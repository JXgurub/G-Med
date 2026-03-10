from rest_framework import serializers
from django.utils.text import slugify
from django.db import transaction
from uuid import uuid4

from apps.users.models import CustomUser
from .models import Clinic, ClinicDepartment, ClinicService
from .models import ClinicStaffMessage, ClinicStaffMessageRecipient


class ClinicSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    doctors_count = serializers.IntegerField(read_only=True)
    patients_count = serializers.IntegerField(read_only=True)
    is_active_status = serializers.BooleanField(read_only=True)
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id',
            'owner',
            'owner_email',
            'owner_passport_id',
            'owner_name',
            'name',
            'slug',
            'description',
            'address',
            'phone_number',
            'email',
            'website',
            'registration_number',
            'license_document',
            'status',
            'is_verified',
            'is_blocked',
            'logo',
            'banner_image',
            'established_date',
            'rating',
            'total_ratings',
            'working_hours',
            'amount',
            'payment_date',
            'created_at',
            'updated_at',
            'doctors_count',
            'patients_count',
            'is_active_status',
            'subscription',
        ]

    def get_owner_name(self, obj):
        return obj.owner.get_full_name() if obj.owner else ''
    
    def get_subscription(self, obj):
        """Include subscription status for clinic owner"""
        if hasattr(obj, 'subscription'):
            subscription = obj.subscription
            # Auto-update expired status
            subscription.auto_deactivate_if_expired()
            subscription.refresh_from_db()
            return {
                'status': subscription.status,
                'is_expired': subscription.is_expired(),
                'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                'days_remaining': subscription.days_remaining(),
                'start_date': subscription.start_date.isoformat() if subscription.start_date else None,
            }
        return None


class ClinicCreateSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(write_only=True)
    owner_password = serializers.CharField(write_only=True)
    owner_first_name = serializers.CharField(write_only=True)
    owner_last_name = serializers.CharField(write_only=True)
    owner_passport_id = serializers.CharField(write_only=True, required=True, allow_blank=False)
    owner_phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    slug = serializers.CharField(required=False, allow_blank=True)
    registration_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Clinic
        fields = [
            'id',
            'owner_email',
            'owner_password',
            'owner_first_name',
            'owner_last_name',
            'owner_passport_id',
            'owner_phone_number',
            'name',
            'slug',
            'description',
            'address',
            'phone_number',
            'email',
            'website',
            'working_hours',
            'registration_number',
            'status',
            'is_verified',
            'is_blocked',
            'established_date',
        ]

    def validate_owner_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value

    def validate_slug(self, value):
        if value and Clinic.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Bu slug allaqachon mavjud.")
        return value

    def validate_owner_passport_id(self, value):
        normalized = ''.join(str(value or '').strip().upper().split())
        if len(normalized) < 5:
            raise serializers.ValidationError("Egasi pasport ID noto'g'ri.")
        return normalized

    def validate_registration_number(self, value):
        normalized = (value or '').strip().upper()
        if not normalized:
            return ''
        if Clinic.objects.filter(registration_number=normalized).exists():
            raise serializers.ValidationError("Bu klinika raqami allaqachon mavjud.")
        return normalized

    def _generate_unique_clinic_number(self):
        # UUID-based suffix minimizes collisions while keeping code short and readable.
        while True:
            candidate = f"CLN-{uuid4().hex[:10].upper()}"
            if not Clinic.objects.filter(registration_number=candidate).exists():
                return candidate

    @transaction.atomic
    def create(self, validated_data):
        owner_email = validated_data.pop('owner_email')
        owner_password = validated_data.pop('owner_password')
        owner_first_name = validated_data.pop('owner_first_name')
        owner_last_name = validated_data.pop('owner_last_name')
        owner_passport_id = validated_data.pop('owner_passport_id')
        owner_phone_number = validated_data.pop('owner_phone_number', '')
        registration_number = (validated_data.get('registration_number') or '').strip().upper()
        validated_data['registration_number'] = registration_number or self._generate_unique_clinic_number()
        validated_data['owner_passport_id'] = owner_passport_id

        slug = validated_data.get('slug')
        if not slug:
            validated_data['slug'] = slugify(validated_data.get('name', 'clinic'))

        owner = CustomUser.objects.create_user(
            username=owner_email,
            email=owner_email,
            password=owner_password,
            first_name=owner_first_name,
            last_name=owner_last_name,
            phone_number=owner_phone_number,
            role='clinic'
        )

        clinic = Clinic.objects.create(owner=owner, **validated_data)
        return clinic


class ClinicStaffMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class ClinicStaffMessageInboxItemSerializer(serializers.ModelSerializer):
    message_id = serializers.UUIDField(source='message.id', read_only=True)
    clinic_id = serializers.UUIDField(source='message.clinic.id', read_only=True)
    clinic_name = serializers.CharField(source='message.clinic.name', read_only=True)
    sender_id = serializers.UUIDField(source='message.sender.id', read_only=True)
    sender_name = serializers.SerializerMethodField()
    body = serializers.CharField(source='message.body', read_only=True)
    created_at = serializers.DateTimeField(source='message.created_at', read_only=True)

    class Meta:
        model = ClinicStaffMessageRecipient
        fields = [
            'id',
            'message_id',
            'clinic_id',
            'clinic_name',
            'sender_id',
            'sender_name',
            'body',
            'created_at',
            'is_read',
            'read_at',
            'delivered_at',
        ]

    def get_sender_name(self, obj):
        sender = getattr(obj.message, 'sender', None)
        if not sender:
            return 'Klinika'
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        return full_name or (sender.email or 'Klinika')


class ClinicDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicDepartment
        fields = [
            'id',
            'clinic',
            'name',
            'description',
            'head_doctor',
            'is_active',
            'created_at',
        ]


class ClinicServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicService
        fields = [
            'id',
            'clinic',
            'department',
            'name',
            'description',
            'price',
            'is_active',
            'created_at',
        ]

class ClinicUpdateSerializer(serializers.ModelSerializer):
    owner_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Clinic
        fields = [
            'id',
            'name',
            'owner_password',
            'description',
            'address',
            'phone_number',
            'email',
            'website',
            'working_hours',
            'status',
            'amount',
            'payment_date',
            'payment_description',
        ]

    def update(self, instance, validated_data):
        owner_password = validated_data.pop('owner_password', None)
        
        # Update clinic fields
        instance = super().update(instance, validated_data)
        
        # Update owner password if provided
        if owner_password:
            instance.owner.set_password(owner_password)
            instance.owner.save()
        
        return instance


class ClinicBannerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ['banner_image']


class ClinicOwnerUpdateSerializer(serializers.ModelSerializer):
    owner_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Clinic
        fields = [
            'name',
            'description',
            'address',
            'phone_number',
            'email',
            'website',
            'working_hours',
            'owner_password',
        ]

    def update(self, instance, validated_data):
        owner_password = validated_data.pop('owner_password', None)
        instance = super().update(instance, validated_data)
        if owner_password:
            instance.owner.set_password(owner_password)
            instance.owner.save(update_fields=['password'])
        return instance