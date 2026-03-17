from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.site_settings.models import SystemAlert
from core.websocket_service import WebSocketService
from .models import Pharmacy, Medicine, PharmacyMarchandise
from .serializers import (
    PharmacySerializer,
    PharmacyCreateSerializer,
    PharmacyUpdateSerializer,
    MedicineSerializer,
    PharmacyMarchandiseSerializer,
)


MEDICINE_NAME_ALERT_TYPE = 'medicine_name_verification'
MEDICINE_NAME_ALERT_MESSAGE = "Bu dori O'zbekiston ichida bormi yoki nomi to'g'ri yozilganmi?"


class PharmacyViewSet(viewsets.ModelViewSet):
    queryset = Pharmacy.objects.select_related('owner').all()
    serializer_class = PharmacySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action == 'my':
            return [permissions.IsAuthenticated()]
        # For create, update, delete - require authentication
        return [permissions.IsAuthenticated()]

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
