from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.utils import timezone

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.permissions.custom_permissions import IsAdministrator, IsClinicOwner
from .models import Clinic, ClinicDepartment, ClinicService, ClinicStaffMessage, ClinicStaffMessageRecipient
from .serializers import (
    ClinicSerializer,
    ClinicCreateSerializer,
    ClinicUpdateSerializer,
    ClinicBannerUpdateSerializer,
    ClinicOwnerUpdateSerializer,
    ClinicStaffMessageCreateSerializer,
    ClinicStaffMessageInboxItemSerializer,
    ClinicDepartmentSerializer,
    ClinicServiceSerializer,
)


class ClinicViewSet(viewsets.ModelViewSet):
    queryset = Clinic.objects.select_related('owner').all()
    serializer_class = ClinicSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['my', 'my_banner', 'my_update', 'my_staff_messages']:
            return [permissions.IsAuthenticated()]
        # For create, update, delete - require admin
        return [permissions.IsAuthenticated(), IsAdministrator()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ClinicCreateSerializer
        if self.action in ['update', 'partial_update']:
            return ClinicUpdateSerializer
        return ClinicSerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)
        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)
        serializer = self.get_serializer(clinic)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['patch'],
        url_path='my/banner',
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[permissions.IsAuthenticated],
    )
    def my_banner(self, request):
        """Clinic owner can upload/update their clinic banner image (фон расм)."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi rasm yuklay oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicBannerUpdateSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ClinicSerializer(clinic, context={'request': request}).data)

    @action(detail=False, methods=['patch'], url_path='my/update')
    def my_update(self, request):
        """Clinic owner can update their own clinic profile and password."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi o\'zgartira oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicOwnerUpdateSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        clinic.refresh_from_db()

        return Response(ClinicSerializer(clinic, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='my/staff-messages')
    def my_staff_messages(self, request):
        """Clinic owner broadcasts a message to all doctors in their clinic."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Faqat klinika egasi yubora oladi.'}, status=403)

        clinic = Clinic.objects.filter(owner=request.user).first()
        if not clinic:
            return Response({'detail': 'Klinika topilmadi.'}, status=404)

        serializer = ClinicStaffMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data['body']

        from apps.doctors.models import Doctor

        doctors = Doctor.objects.select_related('user').filter(clinic=clinic, is_active=True, user__is_active=True)
        recipients = [d.user for d in doctors if d.user]

        if not recipients:
            return Response({'detail': 'Klinikada faol xodimlar topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        message = ClinicStaffMessage.objects.create(clinic=clinic, sender=request.user, body=body)
        recipient_rows = [
            ClinicStaffMessageRecipient(message=message, recipient=u)
            for u in recipients
        ]
        ClinicStaffMessageRecipient.objects.bulk_create(recipient_rows, ignore_conflicts=True)

        # Real-time push (best-effort)
        channel_layer = get_channel_layer()
        payload = {
            'type': 'clinic_staff_message',
            'message_id': str(message.id),
            'clinic_id': str(clinic.id),
            'clinic_name': clinic.name,
            'sender_id': str(request.user.id),
            'sender_name': f"{request.user.first_name or ''} {request.user.last_name or ''}".strip() or request.user.email,
            'body': body,
            'created_at': message.created_at.isoformat(),
        }
        for u in recipients:
            try:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{u.id}',
                    {'type': 'notification_message', 'data': payload},
                )
            except Exception:
                # Ignore push errors; inbox polling still works.
                pass

        return Response({'detail': 'Yuborildi', 'sent': len(recipients)})


class ClinicStaffMessageInboxViewSet(viewsets.GenericViewSet):
    """Doctor inbox for clinic staff messages."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ClinicStaffMessageInboxItemSerializer

    def get_queryset(self):
        user = self.request.user
        return ClinicStaffMessageRecipient.objects.select_related('message', 'message__clinic', 'message__sender').filter(recipient=user)

    def list(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Faqat doktorlar ko‘ra oladi.'}, status=403)

        qs = self.get_queryset()
        unread = request.query_params.get('unread')
        if unread in ('1', 'true', 'True', 'yes'):
            qs = qs.filter(is_read=False)

        limit = request.query_params.get('limit')
        try:
            limit_int = int(limit) if limit else 30
        except (TypeError, ValueError):
            limit_int = 30
        limit_int = max(1, min(limit_int, 200))

        items = qs.order_by('-message__created_at')[:limit_int]
        return Response(self.get_serializer(items, many=True).data)

    @action(detail=True, methods=['patch'], url_path='read')
    def mark_read(self, request, pk=None):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Faqat doktorlar.'}, status=403)

        obj = self.get_queryset().filter(id=pk).first()
        if not obj:
            return Response({'detail': 'Topilmadi.'}, status=404)

        if not obj.is_read:
            obj.is_read = True
            obj.read_at = timezone.now()
            obj.save(update_fields=['is_read', 'read_at'])

        return Response({'detail': 'OK'})


class ClinicDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ClinicDepartment.objects.select_related('clinic', 'head_doctor').all()
    serializer_class = ClinicDepartmentSerializer
    filterset_fields = ['clinic', 'is_active']

    def get_permissions(self):
        # Allow anyone to view departments (list, retrieve)
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        # Require authentication for create, update, delete
        return [permissions.IsAuthenticated()]


class ClinicServiceViewSet(viewsets.ModelViewSet):
    queryset = ClinicService.objects.select_related('clinic', 'department').all()
    serializer_class = ClinicServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['clinic', 'is_active']
