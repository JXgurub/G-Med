from django.shortcuts import get_object_or_404
from django.db import transaction, models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from decimal import Decimal, InvalidOperation
import hashlib
import secrets
import textwrap
import uuid
from datetime import timedelta

from apps.site_settings.models import SystemAlert
from core.websocket_service import WebSocketService
from .models import (
    Pharmacy,
    Medicine,
    PharmacyMarchandise,
    PharmacyPosDevice,
    PharmacySale,
    PharmacySaleLine,
)
from .serializers import (
    PharmacySerializer,
    PharmacyCreateSerializer,
    PharmacyUpdateSerializer,
    MedicineSerializer,
    PharmacyMarchandiseSerializer,
)


MEDICINE_NAME_ALERT_TYPE = 'medicine_name_verification'
MEDICINE_NAME_ALERT_MESSAGE = "Bu dori O'zbekiston ichida bormi yoki nomi to'g'ri yozilganmi?"
POS_ACTIVATION_CODE_LIFETIME = timedelta(minutes=30)


def _get_pos_pharmacy(request):
    if not getattr(request.user, 'is_pharmacy', False):
        return None
    return Pharmacy.objects.filter(owner=request.user).first()


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_snapshot(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    inventory = PharmacyMarchandise.objects.filter(
        pharmacy=pharmacy,
    ).select_related('medicine').order_by('medicine__name', 'expiry_date')
    return Response({
        'pharmacy': {
            'id': str(pharmacy.id),
            'name': pharmacy.name,
            'address': pharmacy.address,
            'phone_number': pharmacy.phone_number,
            'website': pharmacy.website or '',
            'receipt_show_address': pharmacy.receipt_show_address,
            'receipt_show_phone': pharmacy.receipt_show_phone,
            'receipt_show_website': pharmacy.receipt_show_website,
            'receipt_instagram_url': pharmacy.receipt_instagram_url,
            'receipt_show_instagram': pharmacy.receipt_show_instagram,
        },
        'medicines': MedicineSerializer(
            Medicine.objects.filter(is_active=True).order_by('name'),
            many=True,
        ).data,
        'inventory': PharmacyMarchandiseSerializer(inventory, many=True).data,
        'snapshot_at': timezone.now().isoformat(),
    })


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_printer(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        client_uuid = uuid.UUID(str(
            request.data.get('client_id') if request.method == 'POST'
            else request.query_params.get('client_id')
        ))
    except (TypeError, ValueError, AttributeError):
        return Response({'client_id': 'Noto‘g‘ri kassir kompyuteri.'}, status=status.HTTP_400_BAD_REQUEST)

    pos_device = PharmacyPosDevice.objects.filter(
        pharmacy=pharmacy,
        client_id=client_uuid,
        is_active=True,
    ).first()
    from apps.printers.models import PrinterDevice

    printer_device = None
    if pos_device is not None:
        printer_device = PrinterDevice.objects.filter(
            pharmacy=pharmacy,
            pos_device=pos_device,
        ).first()
    shared_printer = PrinterDevice.objects.filter(
        pharmacy=pharmacy,
        pos_device__isnull=True,
    ).order_by('-updated_at').first()
    if printer_device is None:
        printer_device = shared_printer
    if request.method == 'GET':
        now = timezone.now()
        linked_printer_online = bool(
            printer_device
            and printer_device.last_seen
            and 0 <= (now - printer_device.last_seen).total_seconds() <= 90
            and printer_device.status == 'ready'
        )
        shared_printer_online = bool(
            shared_printer
            and shared_printer.last_seen
            and 0 <= (now - shared_printer.last_seen).total_seconds() <= 90
            and shared_printer.status == 'ready'
        )
        if not linked_printer_online and shared_printer_online:
            printer_device = shared_printer
        service_online = bool(
            printer_device
            and printer_device.last_seen
            and 0 <= (now - printer_device.last_seen).total_seconds() <= 90
        )
        return Response({
            'device': {
                'id': str(printer_device.id),
                'device_name': printer_device.device_name,
                'printer_name': printer_device.printer_name,
                'status': printer_device.status,
                'service_online': service_online,
                'printer_ready': service_online and printer_device.status == 'ready',
                'last_seen': printer_device.last_seen.isoformat() if printer_device.last_seen else None,
            } if printer_device else None,
        })

    if pos_device is None:
        return Response({'detail': 'Faol kassir kompyuteri topilmadi.'}, status=status.HTTP_403_FORBIDDEN)

    if not printer_device:
        printer_device = PrinterDevice.objects.create(
            clinic=None,
            pharmacy=pharmacy,
            pos_device=pos_device,
            device_name=pos_device.name,
            device_token=f'gmed-pharmacy-{uuid.uuid4().hex}',
            status='offline',
        )
        response_status = status.HTTP_201_CREATED
    else:
        response_status = status.HTTP_200_OK

    return Response({
        'detail': 'Dorixona printeri sozlandi. Printer Service konfiguratsiyasiga ushbu qiymatlarni kiriting.',
        'device_id': str(printer_device.id),
        'device_token': printer_device.device_token,
        'device_name': printer_device.device_name,
        'pharmacy_id': str(pharmacy.id),
        'pos_device_id': str(pos_device.id),
        'status': printer_device.status,
    }, status=response_status)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_printer_service_register(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona egasi akkaunti topilmadi.'}, status=status.HTTP_403_FORBIDDEN)

    from apps.printers.models import PrinterDevice

    device_name = str(request.data.get('device_name') or '').strip() or 'G-MED Dorixona Printeri'
    if len(device_name) > 120:
        return Response({'device_name': 'Printer nomi 120 belgidan oshmasin.'}, status=status.HTTP_400_BAD_REQUEST)

    printer_device = PrinterDevice.objects.filter(
        pharmacy=pharmacy,
        pos_device__isnull=True,
    ).order_by('-updated_at').first()
    created = printer_device is None
    if created:
        printer_device = PrinterDevice.objects.create(
            clinic=None,
            pharmacy=pharmacy,
            pos_device=None,
            device_name=device_name,
            device_token=f'gmed-pharmacy-{uuid.uuid4().hex}',
            status='offline',
        )
    else:
        printer_device.device_name = device_name
        printer_device.save(update_fields=['device_name', 'updated_at'])

    return Response({
        'detail': 'Dorixona printeri ro‘yxatdan o‘tdi.',
        'device_id': str(printer_device.id),
        'device_token': printer_device.device_token,
        'device_name': printer_device.device_name,
        'pharmacy_id': str(pharmacy.id),
        'status': printer_device.status,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_print_sale(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        sale_uuid = uuid.UUID(str(request.data.get('sale_id')))
        client_uuid = uuid.UUID(str(request.data.get('client_id')))
    except (TypeError, ValueError, AttributeError):
        return Response({'detail': 'Sotuv yoki kassir identifikatori noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

    pos_device = PharmacyPosDevice.objects.filter(
        pharmacy=pharmacy,
        client_id=client_uuid,
        is_active=True,
    ).first()
    if pos_device is None:
        return Response({'detail': 'Faol kassir kompyuteri topilmadi.'}, status=status.HTTP_403_FORBIDDEN)

    sale = PharmacySale.objects.filter(
        pk=sale_uuid,
        pharmacy=pharmacy,
        device=pos_device,
    ).first()
    if sale is None:
        return Response({'detail': 'Sinxronlangan sotuv topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    from apps.printers.models import PrintJob, PrinterDevice

    printer_device = PrinterDevice.objects.filter(
        pharmacy=pharmacy,
        pos_device=pos_device,
    ).first()
    now = timezone.now()
    device_is_ready = bool(
        printer_device
        and printer_device.last_seen
        and 0 <= (now - printer_device.last_seen).total_seconds() <= 90
        and printer_device.status == 'ready'
    )
    if not device_is_ready:
        shared_printer = PrinterDevice.objects.filter(
            pharmacy=pharmacy,
            pos_device__isnull=True,
            status='ready',
            last_seen__gte=now - timedelta(seconds=90),
        ).order_by('-last_seen').first()
        if shared_printer:
            printer_device = shared_printer
    service_online = bool(
        printer_device
        and printer_device.last_seen
        and 0 <= (now - printer_device.last_seen).total_seconds() <= 90
    )
    if not service_online or printer_device.status != 'ready':
        return Response({'detail': 'Dorixona printeri tayyor emas.'}, status=status.HTTP_409_CONFLICT)

    if not sale.lines.exists():
        return Response({'detail': 'Chekda chop etiladigan mahsulot yo‘q.'}, status=status.HTTP_400_BAD_REQUEST)

    def format_receipt_amount(value):
        amount = Decimal(value)
        return f'{int(amount):,}'.replace(',', ' ') if amount == amount.to_integral_value() else f'{amount:.2f}'

    receipt_width = 32

    def wrap_receipt_line(value):
        return textwrap.wrap(
            str(value),
            width=receipt_width,
            break_long_words=True,
            break_on_hyphens=False,
        ) or ['']

    pharmacy_name_lines = wrap_receipt_line(pharmacy.name)
    lines = [
        *pharmacy_name_lines,
        'SOTUV CHEKI',
        '-' * receipt_width,
        f'Chek: {str(sale.id).split("-")[0].upper()}',
        f'Sana: {timezone.localtime(sale.sold_at).strftime("%d.%m.%Y %H:%M")}',
    ]
    if pharmacy.receipt_show_address and pharmacy.address:
        lines.extend(wrap_receipt_line(f'Manzil: {pharmacy.address}'))
    if pharmacy.receipt_show_phone and pharmacy.phone_number:
        lines.extend(wrap_receipt_line(f'Telefon: {pharmacy.phone_number}'))
    if pharmacy.receipt_show_website and pharmacy.website:
        lines.extend(wrap_receipt_line(f'Sayt: {pharmacy.website}'))
    if pharmacy.receipt_show_instagram and pharmacy.receipt_instagram_url:
        lines.extend(wrap_receipt_line(f'Instagram: {pharmacy.receipt_instagram_url}'))
    lines.append('')
    for line in sale.lines.all():
        lines.extend([
            *wrap_receipt_line(line.medicine_name),
            *wrap_receipt_line(
                f'{line.quantity} x {format_receipt_amount(line.unit_price)}'
                f' = {format_receipt_amount(line.line_total)} so\'m'
            ),
        ])
    lines.extend([
        '',
        '-' * receipt_width,
        f"Jami: {format_receipt_amount(sale.total)} so'm",
        '',
        'Xaridingiz uchun rahmat!',
    ])

    job, created = PrintJob.objects.get_or_create(
        sale=sale,
        defaults={
            'clinic': None,
            'pharmacy': pharmacy,
            'printer_device': printer_device,
            'created_by': request.user,
            'status': 'pending',
            'payload': {
                'receipt_type': 'pharmacy',
                'header_line_count': len(pharmacy_name_lines) + 1,
                'receipt_width': receipt_width,
                'lines': lines,
            },
        },
    )
    return Response({
        'detail': 'Chek dorixona printeri navbatiga yuborildi.' if created else 'Chek avval printer navbatiga yuborilgan.',
        'job_id': str(job.id),
        'status': job.status,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_devices(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response([
            {
                'id': str(device.id),
                'name': device.name,
                'is_active': device.is_active,
                'client_id': str(device.client_id) if device.client_id else None,
                'created_at': device.created_at.isoformat(),
                'activated_at': device.activated_at.isoformat() if device.activated_at else None,
                'last_seen_at': device.last_seen_at.isoformat() if device.last_seen_at else None,
                'is_pending': not bool(device.client_id and device.activation_code_hash == ''),
                'stock_discrepancy_count': device.stock_discrepancy_count,
            }
            for device in pharmacy.pos_devices.annotate(
                stock_discrepancy_count=models.Count(
                    'sales',
                    filter=models.Q(sales__has_stock_discrepancy=True),
                )
            )
        ])

    name = str(request.data.get('name') or '').strip()
    if not name:
        return Response({'name': 'Kompyuter nomini kiriting.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(name) > 120:
        return Response({'name': 'Kompyuter nomi 120 belgidan oshmasin.'}, status=status.HTTP_400_BAD_REQUEST)

    activation_code = secrets.token_urlsafe(9)
    device = PharmacyPosDevice.objects.create(
        pharmacy=pharmacy,
        name=name,
        activation_code_hash=hashlib.sha256(activation_code.encode('utf-8')).hexdigest(),
        activation_code_created_at=timezone.now(),
    )
    return Response({
        'id': str(device.id),
        'name': device.name,
        'activation_code': activation_code,
        'expires_at': (device.activation_code_created_at + POS_ACTIVATION_CODE_LIFETIME).isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_device_detail(request, device_id):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
    device = get_object_or_404(PharmacyPosDevice, pk=device_id, pharmacy=pharmacy)
    if device.client_id is None:
        device.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    device.is_active = False
    device.activation_code_hash = ''
    device.save(update_fields=['is_active', 'activation_code_hash'])
    return Response({'id': str(device.id), 'is_active': False}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_activate_device(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    activation_code = str(request.data.get('activation_code') or '').strip()
    client_id = request.data.get('client_id')
    name = str(request.data.get('name') or '').strip()
    if not activation_code or not name:
        return Response(
            {'detail': 'Faollashtirish kodi va kompyuter nomi kerak.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        client_uuid = uuid.UUID(str(client_id))
    except (TypeError, ValueError, AttributeError):
        return Response({'client_id': 'Noto‘g‘ri kompyuter identifikatori.'}, status=status.HTTP_400_BAD_REQUEST)

    code_hash = hashlib.sha256(activation_code.encode('utf-8')).hexdigest()
    with transaction.atomic():
        device = PharmacyPosDevice.objects.select_for_update().filter(
            pharmacy=pharmacy,
            activation_code_hash=code_hash,
            client_id__isnull=True,
        ).first()
        if device is None:
            return Response({'detail': 'Kod noto‘g‘ri yoki ishlatilgan.'}, status=status.HTTP_400_BAD_REQUEST)
        if (
            device.activation_code_created_at is None
            or timezone.now() - device.activation_code_created_at > POS_ACTIVATION_CODE_LIFETIME
        ):
            return Response({'detail': 'Faollashtirish kodi muddati tugagan.'}, status=status.HTTP_400_BAD_REQUEST)

        if PharmacyPosDevice.objects.filter(client_id=client_uuid).exists():
            return Response({'detail': 'Bu kompyuter oldin ro‘yxatdan o‘tgan.'}, status=status.HTTP_409_CONFLICT)

        device.client_id = client_uuid
        device.name = name[:120]
        device.is_active = True
        device.activated_at = timezone.now()
        device.last_seen_at = timezone.now()
        device.activation_code_hash = ''
        device.save(update_fields=[
            'client_id',
            'name',
            'is_active',
            'activated_at',
            'last_seen_at',
            'activation_code_hash',
        ])
    return Response({
        'id': str(device.id),
        'client_id': str(device.client_id),
        'name': device.name,
        'is_active': device.is_active,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def pharmacy_pos_sync_sale(request):
    pharmacy = _get_pos_pharmacy(request)
    if pharmacy is None:
        return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        sale_id = uuid.UUID(str(request.data.get('id')))
    except (TypeError, ValueError, AttributeError):
        return Response({'id': 'Noto‘g‘ri sotuv identifikatori.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client_uuid = uuid.UUID(str(request.data.get('client_id')))
    except (TypeError, ValueError, AttributeError):
        return Response({'client_id': 'Noto‘g‘ri kompyuter identifikatori.'}, status=status.HTTP_400_BAD_REQUEST)

    device = PharmacyPosDevice.objects.filter(
        pharmacy=pharmacy,
        client_id=client_uuid,
        is_active=True,
    ).first()
    if device is None:
        return Response({'detail': 'Kompyuter ro‘yxatdan o‘tmagan yoki o‘chirilgan.'}, status=status.HTTP_403_FORBIDDEN)

    existing_sale = PharmacySale.objects.filter(pk=sale_id).first()
    if existing_sale:
        if existing_sale.pharmacy_id != pharmacy.id or existing_sale.device_id != device.id:
            return Response({'detail': 'Sotuv identifikatori boshqa yozuvda ishlatilgan.'}, status=status.HTTP_409_CONFLICT)
        return Response({
            'id': str(existing_sale.id),
            'synced': True,
            'has_stock_discrepancy': existing_sale.has_stock_discrepancy,
            'already_synced': True,
        })

    lines_data = request.data.get('lines')
    sold_at = parse_datetime(str(request.data.get('sold_at') or ''))
    if not isinstance(lines_data, list) or not lines_data or sold_at is None:
        return Response({'detail': 'Sotuv vaqti hamda dori qatorlari kerak.'}, status=status.HTTP_400_BAD_REQUEST)
    if timezone.is_naive(sold_at):
        sold_at = timezone.make_aware(sold_at, timezone.get_current_timezone())

    try:
        sale_total = Decimal(str(request.data.get('total')))
        if (
            not sale_total.is_finite()
            or sale_total < 0
            or sale_total > Decimal('9999999999.99')
            or sale_total != sale_total.quantize(Decimal('0.01'))
            or len(lines_data) > 500
        ):
            raise ValueError
        parsed_lines = []
        for line in lines_data:
            quantity = int(line.get('quantity'))
            unit_price = Decimal(str(line.get('unit_price')))
            line_total = Decimal(str(line.get('line_total')))
            medicine_name = str(line.get('medicine_name') or '').strip()
            inventory_id = line.get('inventory_id')
            cached_stock_before_sale = line.get('cached_stock_before_sale')
            if cached_stock_before_sale is not None:
                cached_stock_before_sale = int(cached_stock_before_sale)
                if cached_stock_before_sale < 0 or cached_stock_before_sale > 2147483647:
                    raise ValueError
            if inventory_id:
                inventory_id = uuid.UUID(str(inventory_id))
            if (
                quantity < 1
                or quantity > 2147483647
                or not unit_price.is_finite()
                or unit_price < 0
                or unit_price > Decimal('99999999.99')
                or unit_price != unit_price.quantize(Decimal('0.01'))
                or not line_total.is_finite()
                or line_total != unit_price * quantity
                or line_total > Decimal('9999999999.99')
                or not medicine_name
                or len(medicine_name) > 255
            ):
                raise ValueError
            parsed_lines.append((
                inventory_id,
                medicine_name,
                quantity,
                unit_price,
                line_total,
                cached_stock_before_sale,
            ))
        if sum((line[4] for line in parsed_lines), Decimal('0')) != sale_total:
            raise ValueError
    except (AttributeError, TypeError, ValueError, InvalidOperation):
        return Response({'detail': 'Sotuvdagi miqdor yoki narx noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        sale, created = PharmacySale.objects.get_or_create(
            id=sale_id,
            defaults={
                'pharmacy': pharmacy,
                'device': device,
                'sold_at': sold_at,
                'total': sale_total,
            },
        )
        if not created:
            if sale.pharmacy_id != pharmacy.id or sale.device_id != device.id:
                return Response({'detail': 'Sotuv identifikatori boshqa yozuvda ishlatilgan.'}, status=status.HTTP_409_CONFLICT)
            return Response({
                'id': str(sale.id),
                'synced': True,
                'has_stock_discrepancy': sale.has_stock_discrepancy,
                'already_synced': True,
            })
        has_stock_discrepancy = False
        for inventory_id, medicine_name, quantity, unit_price, line_total, cached_stock_before_sale in parsed_lines:
            inventory = None
            if inventory_id:
                inventory = PharmacyMarchandise.objects.select_for_update().filter(
                    pk=inventory_id,
                    pharmacy=pharmacy,
                ).first()
                medicine = inventory.medicine if inventory else None

            available = inventory.quantity_in_stock if inventory and inventory.is_available else 0
            shortfall = max(0, quantity - available)
            if inventory and inventory.is_available:
                inventory.quantity_in_stock = max(0, available - quantity)
                inventory.save(update_fields=['quantity_in_stock', 'updated_at'])
            resulting_stock = inventory.quantity_in_stock if inventory else None
            stock_mismatch = shortfall > 0 or (
                cached_stock_before_sale is not None
                and (
                    resulting_stock is None
                    or resulting_stock != max(0, cached_stock_before_sale - quantity)
                )
            )
            if stock_mismatch:
                has_stock_discrepancy = True

            PharmacySaleLine.objects.create(
                sale=sale,
                inventory=inventory,
                medicine=medicine,
                medicine_name=medicine_name,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                stock_shortfall=shortfall,
                stock_mismatch=stock_mismatch,
            )

        sale.has_stock_discrepancy = has_stock_discrepancy
        sale.save(update_fields=['has_stock_discrepancy'])
        device.last_seen_at = timezone.now()
        device.save(update_fields=['last_seen_at'])

    return Response({
        'id': str(sale.id),
        'synced': True,
        'has_stock_discrepancy': sale.has_stock_discrepancy,
        'already_synced': False,
    }, status=status.HTTP_201_CREATED)


class PharmacyViewSet(viewsets.ModelViewSet):
    queryset = Pharmacy.objects.select_related('owner').all()
    serializer_class = PharmacySerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action == 'my':
            return [permissions.IsAuthenticated()]
        # For create, update, delete - require authentication
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action in {'list', 'retrieve'}:
            return []
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == 'create':
            return PharmacyCreateSerializer
        if self.action in ['update', 'partial_update']:
            return PharmacyUpdateSerializer
        return PharmacySerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=404)
        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=404)
        serializer = self.get_serializer(pharmacy)
        return Response(serializer.data)


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _normalize_name(value):
        return ' '.join(str(value or '').strip().lower().split())

    @staticmethod
    def _can_clear_medicine_base(user):
        return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, 'is_administrator', False)))

    def _collect_vote_stats(self, context):
        votes = context.get('votes') if isinstance(context.get('votes'), dict) else {}
        confirm_count = 0
        correction_vote_count = 0
        grouped_corrections = {}

        for vote in votes.values():
            if not isinstance(vote, dict):
                continue

            vote_type = str(vote.get('type') or '').strip().lower()
            if vote_type == 'confirm':
                confirm_count += 1
                continue

            if vote_type != 'rename':
                continue

            corrected_name = ' '.join(str(vote.get('corrected_name') or '').strip().split())
            normalized_corrected_name = self._normalize_name(corrected_name)
            if not normalized_corrected_name:
                continue

            correction_vote_count += 1
            bucket = grouped_corrections.setdefault(
                normalized_corrected_name,
                {
                    'name': corrected_name,
                    'count': 0,
                },
            )
            bucket['count'] += 1

        leading_correction = None
        if grouped_corrections:
            leading_correction = sorted(
                grouped_corrections.values(),
                key=lambda item: (-item['count'], item['name']),
            )[0]

        eligible_pharmacy_ids = [
            str(pharmacy_id)
            for pharmacy_id in (context.get('eligible_pharmacy_ids') or [])
            if pharmacy_id
        ]
        total_votes = sum(
            1
            for vote in votes.values()
            if isinstance(vote, dict) and str(vote.get('type') or '').strip().lower() in {'confirm', 'rename'}
        )
        eligible_vote_count = len(eligible_pharmacy_ids)
        remaining_vote_count = max(0, eligible_vote_count - total_votes)

        return {
            'votes': votes,
            'confirm_count': confirm_count,
            'correction_vote_count': correction_vote_count,
            'leading_correction_name': leading_correction['name'] if leading_correction else '',
            'leading_correction_count': leading_correction['count'] if leading_correction else 0,
            'eligible_vote_count': eligible_vote_count,
            'remaining_vote_count': remaining_vote_count,
            'total_votes': total_votes,
        }

    def _serialize_name_alert(self, alert, current_pharmacy=None):
        context = alert.context if isinstance(alert.context, dict) else {}
        vote_stats = self._collect_vote_stats(context)
        current_vote = None
        if current_pharmacy is not None:
            votes = vote_stats['votes'] if isinstance(vote_stats.get('votes'), dict) else {}
            current_vote = votes.get(str(current_pharmacy.id))

        return {
            'id': str(alert.id),
            'alert_type': alert.alert_type,
            'message': alert.message,
            'severity': alert.severity,
            'created_at': alert.created_at,
            'medicine_id': context.get('medicine_id'),
            'original_name': context.get('original_name') or context.get('requested_name') or '',
            'reported_by_pharmacy_id': context.get('reported_by_pharmacy_id'),
            'reported_by_pharmacy_name': context.get('reported_by_pharmacy_name') or '',
            'strength': context.get('strength') or '',
            'dosage_form': context.get('dosage_form') or '',
            'category': context.get('category') or 'Boshqa',
            'country_of_origin': context.get('country_of_origin') or '',
            'confirm_count': vote_stats['confirm_count'],
            'correction_vote_count': vote_stats['correction_vote_count'],
            'leading_correction_name': vote_stats['leading_correction_name'],
            'leading_correction_count': vote_stats['leading_correction_count'],
            'eligible_vote_count': vote_stats['eligible_vote_count'],
            'remaining_vote_count': vote_stats['remaining_vote_count'],
            'current_user_vote_type': current_vote.get('type') if isinstance(current_vote, dict) else '',
            'current_user_corrected_name': current_vote.get('corrected_name') if isinstance(current_vote, dict) else '',
        }

    def _find_open_name_alert(self, normalized_name):
        for alert in SystemAlert.objects.filter(
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            is_resolved=False,
        ).order_by('-created_at'):
            context = alert.context if isinstance(alert.context, dict) else {}
            if self._normalize_name(context.get('normalized_name')) == normalized_name:
                return alert
        return None

    def _notify_other_pharmacies_about_name(self, medicine, reporter_pharmacy):
        normalized_name = self._normalize_name(medicine.name)
        if not normalized_name or reporter_pharmacy is None:
            return None, False

        existing_alert = self._find_open_name_alert(normalized_name)
        if existing_alert:
            return existing_alert, False

        other_pharmacies = list(
            Pharmacy.objects.select_related('owner').exclude(pk=reporter_pharmacy.pk)
        )
        if not other_pharmacies:
            return None, False

        context = {
            'medicine_id': str(medicine.id),
            'original_name': medicine.name,
            'normalized_name': normalized_name,
            'strength': medicine.strength,
            'dosage_form': medicine.dosage_form,
            'category': medicine.category,
            'country_of_origin': medicine.country_of_origin,
            'reported_by_pharmacy_id': str(reporter_pharmacy.id),
            'reported_by_pharmacy_name': reporter_pharmacy.name,
            'reported_by_user_id': str(reporter_pharmacy.owner_id),
            'eligible_pharmacy_ids': [str(pharmacy.id) for pharmacy in other_pharmacies],
            'eligible_user_ids': [str(pharmacy.owner_id) for pharmacy in other_pharmacies if pharmacy.owner_id],
            'votes': {},
        }
        alert = SystemAlert.objects.create(
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            message=MEDICINE_NAME_ALERT_MESSAGE,
            severity=SystemAlert.Severity.WARNING,
            context=context,
        )

        for pharmacy in other_pharmacies:
            if not pharmacy.owner_id:
                continue
            WebSocketService.send_notification(
                pharmacy.owner_id,
                'medicine_name_verification_created',
                {
                    'alert_id': str(alert.id),
                    'message': MEDICINE_NAME_ALERT_MESSAGE,
                    'original_name': medicine.name,
                    'reported_by_pharmacy_name': reporter_pharmacy.name,
                },
            )

        return alert, True

    def _get_pending_name_alert(self, alert_id, pharmacy):
        alert = get_object_or_404(
            SystemAlert,
            pk=alert_id,
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            is_resolved=False,
        )
        context = alert.context if isinstance(alert.context, dict) else {}
        if str(context.get('reported_by_pharmacy_id') or '') == str(pharmacy.id):
            return None, Response({'detail': 'O\'z xabaringizni o\'zingiz tekshira olmaysiz.'}, status=status.HTTP_403_FORBIDDEN)

        return alert, None

    def _save_name_vote(self, alert, pharmacy, vote_type, corrected_name=''):
        context = alert.context if isinstance(alert.context, dict) else {}
        votes = context.get('votes') if isinstance(context.get('votes'), dict) else {}
        clean_name = ' '.join(str(corrected_name or '').strip().split())

        votes[str(pharmacy.id)] = {
            'pharmacy_id': str(pharmacy.id),
            'pharmacy_name': pharmacy.name,
            'user_id': str(pharmacy.owner_id) if pharmacy.owner_id else '',
            'type': vote_type,
            'corrected_name': clean_name,
            'voted_at': timezone.now().isoformat(),
        }
        context['votes'] = votes
        context['last_voted_at'] = timezone.now().isoformat()
        alert.context = context
        alert.save(update_fields=['context'])
        return context

    @staticmethod
    def _has_pharmacy_voted(alert_context, pharmacy_id):
        if not isinstance(alert_context, dict) or pharmacy_id is None:
            return False
        votes = alert_context.get('votes') if isinstance(alert_context.get('votes'), dict) else {}
        return str(pharmacy_id) in votes

    def _merge_medicine_records(self, source_medicine, target_medicine):
        for stock in PharmacyMarchandise.objects.filter(medicine=source_medicine):
            existing_stock = PharmacyMarchandise.objects.filter(
                pharmacy=stock.pharmacy,
                medicine=target_medicine,
                batch_number=stock.batch_number,
            ).exclude(pk=stock.pk).first()

            if existing_stock:
                existing_stock.quantity_in_stock += stock.quantity_in_stock
                if stock.expiry_date and stock.expiry_date > existing_stock.expiry_date:
                    existing_stock.expiry_date = stock.expiry_date
                existing_stock.is_available = existing_stock.is_available or stock.is_available
                if stock.unit_price and not existing_stock.unit_price:
                    existing_stock.unit_price = stock.unit_price
                existing_stock.save(update_fields=['quantity_in_stock', 'expiry_date', 'is_available', 'unit_price'])
                stock.delete()
            else:
                stock.medicine = target_medicine
                stock.save(update_fields=['medicine'])

        source_medicine.delete()

    def _resolve_medicine_name(self, medicine, resolved_name):
        clean_name = ' '.join(str(resolved_name or '').strip().split())
        if not clean_name or self._normalize_name(clean_name) == self._normalize_name(medicine.name):
            return medicine

        merge_target = Medicine.objects.filter(
            name__iexact=clean_name,
            strength__iexact=medicine.strength,
            dosage_form__iexact=medicine.dosage_form,
            category__iexact=medicine.category,
        ).exclude(pk=medicine.pk).first()

        if merge_target:
            self._merge_medicine_records(medicine, merge_target)
            return merge_target

        medicine.name = clean_name
        medicine.save(update_fields=['name'])
        return medicine

    def _build_resolution_response(self, alert, resolved_medicine, resolution_type):
        context = alert.context if isinstance(alert.context, dict) else {}
        vote_stats = self._collect_vote_stats(context)
        return {
            'id': str(alert.id),
            'resolved': True,
            'resolution_type': resolution_type,
            'corrected_name': resolved_medicine.name,
            'medicine_id': str(resolved_medicine.id),
            'confirm_count': vote_stats['confirm_count'],
            'correction_vote_count': vote_stats['correction_vote_count'],
            'leading_correction_name': vote_stats['leading_correction_name'],
            'leading_correction_count': vote_stats['leading_correction_count'],
        }

    def _finalize_name_alert(self, alert, acting_user, resolution_type, resolved_name):
        with transaction.atomic():
            alert = SystemAlert.objects.select_for_update().get(pk=alert.pk)
            context = alert.context if isinstance(alert.context, dict) else {}
            medicine_id = context.get('medicine_id')
            if not medicine_id:
                raise ValueError('Biriktirilgan dori topilmadi.')

            medicine = get_object_or_404(Medicine.objects.select_for_update(), pk=medicine_id)
            resolved_medicine = self._resolve_medicine_name(medicine, resolved_name)
            vote_stats = self._collect_vote_stats(context)

            context.update({
                'resolved_name': resolved_medicine.name,
                'corrected_name': resolved_medicine.name,
                'resolved_medicine_id': str(resolved_medicine.id),
                'resolution_type': resolution_type,
                'confirm_count': vote_stats['confirm_count'],
                'correction_vote_count': vote_stats['correction_vote_count'],
                'leading_correction_name': vote_stats['leading_correction_name'],
                'leading_correction_count': vote_stats['leading_correction_count'],
                'total_votes': vote_stats['total_votes'],
            })
            alert.context = context
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = acting_user
            alert.save(update_fields=['context', 'is_resolved', 'resolved_at', 'resolved_by'])

        payload = {
            'alert_id': str(alert.id),
            'original_name': context.get('original_name') or '',
            'corrected_name': resolved_medicine.name,
            'resolution_type': resolution_type,
            'confirm_count': context.get('confirm_count', 0),
            'correction_vote_count': context.get('correction_vote_count', 0),
            'leading_correction_name': context.get('leading_correction_name') or '',
            'leading_correction_count': context.get('leading_correction_count', 0),
        }
        notified_user_ids = set(context.get('eligible_user_ids') or [])
        reporter_user_id = context.get('reported_by_user_id')
        if reporter_user_id:
            notified_user_ids.add(str(reporter_user_id))

        for user_id in notified_user_ids:
            if not user_id:
                continue
            WebSocketService.send_notification(
                user_id,
                'medicine_name_verification_resolved',
                payload,
            )

        return self._build_resolution_response(alert, resolved_medicine, resolution_type)

    def _check_if_alert_can_resolve(self, alert, acting_user):
        context = alert.context if isinstance(alert.context, dict) else {}
        vote_stats = self._collect_vote_stats(context)
        original_name = ' '.join(str(context.get('original_name') or '').strip().split())
        confirm_count = vote_stats['confirm_count']
        leading_correction_name = vote_stats['leading_correction_name']
        leading_correction_count = vote_stats['leading_correction_count']
        remaining_vote_count = vote_stats['remaining_vote_count']

        if confirm_count > leading_correction_count + remaining_vote_count:
            return self._finalize_name_alert(alert, acting_user, 'kept_original', original_name)

        if leading_correction_name and leading_correction_count > confirm_count + remaining_vote_count:
            return self._finalize_name_alert(alert, acting_user, 'renamed', leading_correction_name)

        if vote_stats['eligible_vote_count'] > 0 and vote_stats['total_votes'] >= vote_stats['eligible_vote_count']:
            if leading_correction_name and leading_correction_count > confirm_count:
                return self._finalize_name_alert(alert, acting_user, 'renamed', leading_correction_name)
            return self._finalize_name_alert(alert, acting_user, 'kept_original', original_name)

        return {
            'id': str(alert.id),
            'resolved': False,
            'confirm_count': vote_stats['confirm_count'],
            'correction_vote_count': vote_stats['correction_vote_count'],
            'leading_correction_name': vote_stats['leading_correction_name'],
            'leading_correction_count': vote_stats['leading_correction_count'],
            'remaining_vote_count': vote_stats['remaining_vote_count'],
        }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_name = str(serializer.validated_data.get('name') or '').strip()
        name_exists_before = bool(
            requested_name and Medicine.objects.filter(name__iexact=requested_name).exists()
        )

        self.perform_create(serializer)
        instance = serializer.instance
        response_data = self.get_serializer(instance).data
        response_data['name_verification_alert_created'] = False

        reporter_pharmacy = None
        if request.user.is_authenticated and getattr(request.user, 'is_pharmacy', False):
            reporter_pharmacy = Pharmacy.objects.filter(owner=request.user).first()

        if instance and reporter_pharmacy and requested_name and not name_exists_before:
            alert, created = self._notify_other_pharmacies_about_name(instance, reporter_pharmacy)
            response_data['name_verification_alert_created'] = created
            response_data['name_verification_alert_id'] = str(alert.id) if alert else None

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated], url_path='name-alerts')
    def name_alerts(self, request):
        if not getattr(request.user, 'is_pharmacy', False):
            return Response({'detail': 'Faqat dorixona foydalanuvchisi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        alerts = []
        for alert in SystemAlert.objects.filter(
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            is_resolved=False,
        ).order_by('-created_at'):
            context = alert.context if isinstance(alert.context, dict) else {}
            if str(context.get('reported_by_pharmacy_id') or '') == str(pharmacy.id):
                continue
            if self._has_pharmacy_voted(context, pharmacy.id):
                continue
            alerts.append(self._serialize_name_alert(alert, current_pharmacy=pharmacy))

        return Response(alerts, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['patch'],
        permission_classes=[permissions.IsAuthenticated],
        url_path=r'name-alerts/(?P<alert_id>[^/.]+)/confirm',
    )
    def confirm_name_alert(self, request, alert_id=None):
        if not getattr(request.user, 'is_pharmacy', False):
            return Response({'detail': 'Faqat dorixona foydalanuvchisi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        alert, error_response = self._get_pending_name_alert(alert_id, pharmacy)
        if error_response is not None:
            return error_response

        self._save_name_vote(alert, pharmacy, 'confirm')
        response_data = self._check_if_alert_can_resolve(alert, request.user)
        return Response(response_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['patch'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='name-alerts/confirm-all',
    )
    def confirm_all_name_alerts(self, request):
        if not getattr(request.user, 'is_pharmacy', False):
            return Response({'detail': 'Faqat dorixona foydalanuvchisi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        alerts = []
        for alert in SystemAlert.objects.filter(
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            is_resolved=False,
        ).order_by('-created_at'):
            context = alert.context if isinstance(alert.context, dict) else {}
            if str(context.get('reported_by_pharmacy_id') or '') == str(pharmacy.id):
                continue
            if self._has_pharmacy_voted(context, pharmacy.id):
                continue
            alerts.append(alert)

        resolved_count = 0
        voted_count = 0
        resolved_alert_ids = []

        for alert in alerts:
            self._save_name_vote(alert, pharmacy, 'confirm')
            response_data = self._check_if_alert_can_resolve(alert, request.user)
            voted_count += 1
            if response_data.get('resolved'):
                resolved_count += 1
                resolved_alert_ids.append(str(alert.id))

        return Response(
            {
                'processed_count': voted_count,
                'resolved_count': resolved_count,
                'remaining_count': max(0, len(alerts) - voted_count),
                'resolved_alert_ids': resolved_alert_ids,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['patch'],
        permission_classes=[permissions.IsAuthenticated],
        url_path=r'name-alerts/(?P<alert_id>[^/.]+)/correct',
    )
    def correct_name_alert(self, request, alert_id=None):
        if not getattr(request.user, 'is_pharmacy', False):
            return Response({'detail': 'Faqat dorixona foydalanuvchisi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        corrected_name = str(request.data.get('name') or '').strip()
        if not corrected_name:
            return Response({'detail': 'To\'g\'ri dori nomini kiriting.'}, status=status.HTTP_400_BAD_REQUEST)

        alert, error_response = self._get_pending_name_alert(alert_id, pharmacy)
        if error_response is not None:
            return error_response

        context = alert.context if isinstance(alert.context, dict) else {}
        if self._normalize_name(corrected_name) == self._normalize_name(context.get('original_name')):
            self._save_name_vote(alert, pharmacy, 'confirm')
        else:
            self._save_name_vote(alert, pharmacy, 'rename', corrected_name=corrected_name)

        response_data = self._check_if_alert_can_resolve(alert, request.user)
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated], url_path='clear-all')
    def clear_all(self, request):
        if not self._can_clear_medicine_base(request.user):
            return Response({'detail': 'Faqat admin medicine bazasini tozalay oladi.'}, status=status.HTTP_403_FORBIDDEN)

        deleted_count = Medicine.objects.count()
        inventory_count = PharmacyMarchandise.objects.count()
        Medicine.objects.all().delete()

        SystemAlert.objects.filter(
            alert_type=MEDICINE_NAME_ALERT_TYPE,
            is_resolved=False,
        ).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user,
        )

        return Response(
            {
                'deleted_count': deleted_count,
                'deleted_inventory_count': inventory_count,
            },
            status=status.HTTP_200_OK,
        )


class PharmacyMarchandiseViewSet(viewsets.ModelViewSet):
    queryset = PharmacyMarchandise.objects.select_related('pharmacy', 'medicine').all()
    serializer_class = PharmacyMarchandiseSerializer
    filterset_fields = ['pharmacy', 'medicine', 'is_available']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_pharmacy', False):
            return queryset.filter(pharmacy__owner=user)
        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated], url_path='clear-all')
    def clear_all(self, request):
        if not request.user.is_pharmacy:
            return Response({'detail': 'Faqat dorixona egasi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        qs = PharmacyMarchandise.objects.filter(pharmacy=pharmacy)
        deleted_count = qs.count()
        qs.delete()

        return Response({'deleted_count': deleted_count}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def medicine_search(request):
    """
    Search medicines by name prefix.
    Query parameters:
    - q: search query (minimum 1 character)
    - limit: maximum number of results (default 10)
    """
    query = request.query_params.get('q', '').strip()
    try:
        limit = min(int(request.query_params.get('limit', 10)), 50)
    except (TypeError, ValueError):
        limit = 10

    if not query or len(query) < 1:
        return Response([], status=status.HTTP_200_OK)

    medicines = Medicine.objects.filter(
        is_active=True
    ).filter(
        models.Q(name__istartswith=query) |
        models.Q(generic_name__istartswith=query)
    ).annotate(
        prefix_priority=models.Case(
            models.When(name__istartswith=query, then=models.Value(0)),
            models.When(generic_name__istartswith=query, then=models.Value(1)),
            default=models.Value(2),
            output_field=models.IntegerField(),
        )
    ).order_by('prefix_priority', 'name')[:limit]

    serializer = MedicineSerializer(medicines, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
