import uuid
from datetime import datetime

from django.core import signing
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from apps.clinics.models import Clinic, ClinicDepartment, ReceptionStaff
from apps.medical.models import Appointment
from .models import PrinterDevice, PrintJob


class PrinterHeartbeatSerializer(serializers.Serializer):
    service_online = serializers.BooleanField(required=False, default=True)
    printer_connected = serializers.BooleanField(required=False, default=False)
    printer_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    printer_status = serializers.CharField(required=False, allow_blank=True, default='offline')
    device_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    clinic_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    reception_room_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_seen = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    service_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PrinterJobStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['pending', 'printing', 'completed', 'failed'])
    error_message = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    device_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    clinic_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    reception_room_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    device_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    printed_at = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PrinterDeviceViewSet(viewsets.ModelViewSet):
    queryset = PrinterDevice.objects.select_related('clinic', 'reception_room').all()
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in {'register', 'my_status'}:
            return [permissions.AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'clinic':
            clinic = getattr(user, 'clinic', None)
            if clinic:
                return PrinterDevice.objects.filter(clinic=clinic).select_related('clinic', 'reception_room')
        return PrinterDevice.objects.none()

    @staticmethod
    def _resolve_clinic_from_request(request):
        user = request.user
        clinic = None

        if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'clinic':
            clinic = getattr(user, 'clinic', None)
        elif getattr(user, 'is_authenticated', False):
            clinic = Clinic.objects.filter(owner=user).first()

        if not clinic:
            raw_token = str(request.headers.get('X-Reception-Session') or '').strip()
            if raw_token:
                try:
                    payload = signing.loads(raw_token, salt='reception-staff-session', max_age=60 * 60 * 12)
                    staff = ReceptionStaff.objects.select_related('clinic').filter(id=payload['staff_id'], clinic_id=payload['clinic_id'], is_active=True).first()
                    if staff:
                        clinic = staff.clinic
                except Exception:
                    clinic = None

        return clinic

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='my-status', throttle_classes=[])
    def my_status(self, request):
        clinic = self._resolve_clinic_from_request(request)
        clinic_id = str(request.query_params.get('clinic_id') or '').strip()
        if clinic_id and not clinic:
            clinic = Clinic.objects.filter(id=clinic_id).first()

        if not clinic:
            return Response({'detail': 'Klinika yoki qabulxona sessiyasi topilmadi.'}, status=status.HTTP_403_FORBIDDEN)

        devices = PrinterDevice.objects.filter(clinic=clinic).select_related('clinic', 'reception_room').order_by('-updated_at')
        data = []
        now = timezone.now()
        for device in devices:
            service_online = device.last_seen is not None and (now - device.last_seen).total_seconds() <= 90
            printer_ready = device.status in {'ready', 'checking'}
            if device.status == 'ready':
                status_label = '🟢 Printer: Ulangan va tayyor'
            elif device.status in {'checking'}:
                status_label = '🟡 Printer: Tekshirilmoqda / band'
            elif device.status == 'offline':
                status_label = '🔴 Printer Service offline'
            elif service_online and not printer_ready:
                status_label = '🟠 Printer Service online, lekin ulanmagan'
            else:
                status_label = '🔴 Printer: Ulanmagan'
            data.append({
                'id': str(device.id),
                'device_name': device.device_name,
                'printer_name': device.printer_name,
                'device_token': device.device_token,
                'status': device.status,
                'status_label': status_label,
                'service_online': service_online,
                'printer_connected': printer_ready,
                'printer_ready': printer_ready,
                'last_seen': device.last_seen.isoformat() if device.last_seen else None,
            })
        return Response({'devices': data})

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny], url_path='register', throttle_classes=[])
    def register(self, request):
        clinic = self._resolve_clinic_from_request(request)
        clinic_id = str(request.data.get('clinic_id') or '').strip() or (str(clinic.id) if clinic else '')
        if not clinic_id:
            return Response({'detail': 'Klinika ID kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        if not clinic:
            clinic = Clinic.objects.filter(id=clinic_id).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        reception_room_id = str(request.data.get('reception_room_id') or '').strip()
        reception_room = None
        if reception_room_id:
            reception_room = ClinicDepartment.objects.filter(id=reception_room_id, clinic=clinic).first()
        if reception_room_id and not reception_room:
            return Response({'detail': 'Qabulxona bo‘limi topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if not reception_room:
            reception_room = ClinicDepartment.objects.filter(clinic=clinic).order_by('name').first()

        device_name = str(request.data.get('device_name') or '').strip() or 'G-MED Printer Device'
        existing_device = PrinterDevice.objects.filter(clinic=clinic, reception_room=reception_room).order_by('-updated_at').first()
        if existing_device and existing_device.device_token:
            existing_device.device_name = device_name
            existing_device.save(update_fields=['device_name', 'updated_at'])
            return Response({
                'detail': 'Printer allaqachon ro‘yxatdan o‘tilgan.',
                'device_id': str(existing_device.id),
                'device_token': existing_device.device_token,
                'clinic_id': str(clinic.id),
                'reception_room_id': str(reception_room.id) if reception_room else None,
                'status': existing_device.status,
            })

        for _ in range(10):
            token_parts = [
                'gmed',
                str(clinic.id).replace('-', ''),
                str(reception_room.id).replace('-', '') if reception_room else 'main',
                uuid.uuid4().hex[:16],
            ]
            candidate = '-'.join(token_parts)
            if not PrinterDevice.objects.filter(device_token=candidate).exists():
                device_token = candidate
                break
        else:
            device_token = f"gmed-{uuid.uuid4().hex}"

        device = PrinterDevice.objects.create(
            clinic=clinic,
            reception_room=reception_room,
            device_name=device_name,
            device_token=device_token,
            status='offline',
            printer_name='',
        )

        return Response({
            'detail': 'Printer uchun token yaratildi.',
            'device_id': str(device.id),
            'device_token': device.device_token,
            'clinic_id': str(clinic.id),
            'reception_room_id': str(reception_room.id) if reception_room else None,
            'status': device.status,
        })


class PrintJobViewSet(viewsets.ModelViewSet):
    queryset = PrintJob.objects.select_related('clinic', 'reception_room', 'printer_device', 'appointment', 'created_by').all()
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in {'pending', 'status_update', 'retry', 'test_print'}:
            return [permissions.AllowAny()]
        return [permission() for permission in self.permission_classes]

    def _get_clinic_from_request(self):
        user = self.request.user
        if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'clinic':
            clinic = getattr(user, 'clinic', None)
            if clinic:
                return clinic

        if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) in {'clinic', 'superuser', 'staff'}:
            clinic = Clinic.objects.filter(owner=user).first()
            if clinic:
                return clinic

        raw_token = str(self.request.headers.get('X-Reception-Session') or '').strip()
        if raw_token:
            try:
                payload = signing.loads(raw_token, salt='reception-staff-session', max_age=60 * 60 * 12)
                staff = ReceptionStaff.objects.select_related('clinic').filter(
                    id=payload['staff_id'],
                    clinic_id=payload['clinic_id'],
                    is_active=True,
                ).first()
                if staff:
                    return staff.clinic
            except Exception:
                return None
        return None

    @staticmethod
    def _get_device_token_from_request(request, data=None):
        header_token = str(request.headers.get('X-Device-Token') or '').strip()
        if header_token:
            return header_token

        if isinstance(data, dict):
            payload_token = str(data.get('device_id') or '').strip()
            if payload_token:
                return payload_token

        payload_data = getattr(request, 'data', None)
        if isinstance(payload_data, dict):
            payload_token = str(payload_data.get('device_id') or '').strip()
            if payload_token:
                return payload_token

        query_token = str(request.query_params.get('device_token') or '').strip()
        return query_token

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'clinic':
            clinic = getattr(user, 'clinic', None)
            if clinic:
                return PrintJob.objects.filter(clinic=clinic).select_related('clinic', 'reception_room', 'printer_device', 'appointment', 'created_by')
        return PrintJob.objects.none()

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny], url_path='pending', throttle_classes=[])
    def pending(self, request):
        device_token = str(request.query_params.get('device_token', '') or '').strip()
        clinic_id = str(request.query_params.get('clinic_id', '') or '').strip()
        reception_room_id = str(request.query_params.get('reception_room_id', '') or '').strip()

        if not device_token:
            return Response({'detail': 'Device token kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = PrintJob.objects.filter(status='pending')
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        if reception_room_id:
            qs = qs.filter(reception_room_id=reception_room_id)

        device = get_object_or_404(PrinterDevice, device_token=device_token)
        qs = qs.filter(clinic_id=device.clinic_id)
        if device.reception_room_id:
            qs = qs.filter(reception_room_id=device.reception_room_id)

        jobs = []
        for job in qs.order_by('created_at')[:20]:
            jobs.append({
                'id': str(job.id),
                'clinic_id': str(job.clinic_id),
                'reception_room_id': str(job.reception_room_id) if job.reception_room_id else None,
                'printer_device_id': str(job.printer_device_id) if job.printer_device_id else None,
                'appointment_id': str(job.appointment_id) if job.appointment_id else None,
                'payload': job.payload,
                'status': job.status,
            })
        return Response({'jobs': jobs})

    @action(detail=True, methods=['patch'], permission_classes=[permissions.AllowAny], url_path='status', throttle_classes=[])
    def status_update(self, request, pk=None):
        serializer = PrinterJobStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        device_token = self._get_device_token_from_request(request, data)
        if not device_token:
            return Response({'detail': 'Device token kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        device = PrinterDevice.objects.select_related('clinic', 'reception_room').filter(device_token=device_token).first()
        if not device:
            return Response({'detail': 'Qurilma topilmadi.'}, status=status.HTTP_403_FORBIDDEN)

        job = PrintJob.objects.select_related('clinic', 'reception_room', 'printer_device').filter(pk=pk).first()
        if not job:
            return Response({'detail': 'Job topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        if job.clinic_id != device.clinic_id:
            return Response({'detail': 'Qurilma klinikaga mos emas.'}, status=status.HTTP_403_FORBIDDEN)

        if device.reception_room_id and job.reception_room_id and job.reception_room_id != device.reception_room_id:
            return Response({'detail': 'Qurilma qabulxona bilan mos emas.'}, status=status.HTTP_403_FORBIDDEN)

        if data['status'] == 'completed':
            job.status = 'completed'
            job.printed_at = timezone.now()
        elif data['status'] == 'failed':
            job.status = 'failed'
            job.error_message = data.get('error_message') or ''
        elif data['status'] == 'printing':
            job.status = 'printing'
        else:
            job.status = data['status']

        job.printer_device = device
        job.clinic_id = device.clinic_id
        if device.reception_room_id:
            job.reception_room_id = device.reception_room_id

        job.save(update_fields=['status', 'error_message', 'printer_device', 'clinic', 'reception_room', 'printed_at'])
        return Response({'detail': 'Print job status updated', 'status': job.status})

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny], url_path='retry')
    def retry(self, request, pk=None):
        user = request.user
        clinic = None
        if getattr(user, 'is_authenticated', False):
            clinic = getattr(user, 'clinic', None) or Clinic.objects.filter(owner=user).first()

        job = PrintJob.objects.select_related('clinic').filter(pk=pk).first()
        if not job:
            return Response({'detail': 'Job topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if clinic and job.clinic_id != clinic.id:
            return Response({'detail': 'Klinika bilan mos kelmaydi.'}, status=status.HTTP_403_FORBIDDEN)

        if job.status != 'failed':
            return Response({'detail': 'Faqat failed holatidagi jobni qayta chop etish mumkin.', 'status': job.status}, status=status.HTTP_400_BAD_REQUEST)

        job.status = 'pending'
        job.error_message = ''
        job.printed_at = None
        job.save(update_fields=['status', 'error_message', 'printed_at'])
        return Response({'detail': 'Print job qayta navbatga qo‘shildi.', 'status': job.status, 'job_id': str(job.id)})

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny], url_path='test-print', throttle_classes=[])
    def test_print(self, request):
        clinic = self._get_clinic_from_request()
        if not clinic:
            user = request.user
            if getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'clinic':
                clinic = getattr(user, 'clinic', None)
            if not clinic:
                return Response({'detail': 'Klinika yoki qabulxona sessiyasi topilmadi.'}, status=status.HTTP_401_UNAUTHORIZED)

        device = PrinterDevice.objects.filter(clinic=clinic).order_by('-updated_at').first()
        if not device:
            return Response({'detail': 'Ulangan printer topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'lines': [
                '================================',
                '            G-MED',
                '      TEST CHOP ETISH',
                '================================',
                '',
                f'Klinika: {clinic.name}',
                f'Qabulxona: {device.reception_room.name if device.reception_room else "Main"}',
                f'Sana: {datetime.now().strftime("%d.%m.%Y")}',
                f'Vaqt: {datetime.now().strftime("%H:%M")}',
                '',
                'Printer muvaffaqiyatli ulangan.',
                '================================',
            ]
        }

        created_by = getattr(request.user, 'is_authenticated', False) and request.user or None
        job = PrintJob.objects.create(
            clinic=clinic,
            reception_room=device.reception_room,
            printer_device=device,
            created_by=created_by,
            status='pending',
            payload=payload,
        )
        return Response({'detail': 'Test print job yaratildi.', 'job_id': str(job.id)})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([])
def printer_heartbeat(request):
    serializer = PrinterHeartbeatSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    device_token = str(data.get('device_id') or '').strip()
    if not device_token:
        return Response({'detail': 'Device token kerak.'}, status=status.HTTP_400_BAD_REQUEST)

    clinic_id = data.get('clinic_id')
    reception_room_id = data.get('reception_room_id')
    device = PrinterDevice.objects.filter(device_token=device_token).first()
    if not device:
        if not clinic_id:
            return Response({'detail': 'Clinic ID kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        clinic = get_object_or_404(Clinic, id=clinic_id)
        reception_room = None
        if reception_room_id:
            reception_room = ClinicDepartment.objects.filter(id=reception_room_id, clinic=clinic).first()
        device = PrinterDevice.objects.create(
            clinic=clinic,
            reception_room=reception_room,
            device_name='G-MED Printer Device',
            printer_name=data.get('printer_name') or 'Xprinter',
            device_token=device_token,
            status='offline',
        )

    service_online = bool(data.get('service_online', True))
    printer_connected = bool(data.get('printer_connected', False))
    device.printer_name = data.get('printer_name') or device.printer_name
    device.status = 'ready' if service_online and printer_connected else 'offline' if not service_online else 'disconnected'
    device.last_seen = timezone.now()
    if clinic_id:
        device.clinic_id = clinic_id
    if reception_room_id:
        device.reception_room_id = reception_room_id
    device.save(update_fields=['printer_name', 'status', 'last_seen', 'clinic', 'reception_room'])

    return Response({'detail': 'Heartbeat received', 'device_id': str(device.id), 'status': device.status, 'service_online': service_online, 'printer_connected': printer_connected})
