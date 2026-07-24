from rest_framework import serializers
from django.db import transaction
from uuid import uuid4

from apps.users.models import CustomUser
from apps.users.serializers import UserSerializer
from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'user',
            'clinics',
            'gender',
            'date_of_birth',
            'birth_year',
            'age',
            'blood_type',
            'insurance_id',
            'phone_number',
            'address',
            'city',
            'country',
            'emergency_contact_name',
            'emergency_contact_phone',
            'allergies',
            'drug_allergies',
            'animal_allergies',
            'weight_kg',
            'height_cm',
            'chronic_diseases',
            'medications',
            'is_active',
            'created_at',
            'updated_at',
        ]


class PatientCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Patient
        fields = [
            'id',
            'email',
            'password',
            'first_name',
            'last_name',
            'phone_number',
            'gender',
            'date_of_birth',
            'birth_year',
            'age',
            'blood_type',
            'insurance_id',
            'address',
            'city',
            'country',
            'emergency_contact_name',
            'emergency_contact_phone',
            'allergies',
            'drug_allergies',
            'animal_allergies',
            'weight_kg',
            'height_cm',
            'chronic_diseases',
            'medications',
        ]

    def validate_email(self, value):
        value = (value or '').strip()
        if not value:
            return value
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        email = (validated_data.pop('email') or '').strip()
        if not email:
            email = f"patient_{uuid4().hex[:12]}@hospitoll.local"
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        phone_number = validated_data.pop('phone_number', '')

        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role='patient'
        )

        patient = Patient.objects.create(user=user, **validated_data)
        return patient
