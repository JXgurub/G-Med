from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor, DoctorAvailability
from .models import Appointment, MedicalRecord, Diagnosis, Prescription, LabTest


class DoctorDetailsSerializer(serializers.Serializer):
    """Nested doctor details"""
    id = serializers.UUIDField()
    full_name = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()
    
    def get_full_name(self, obj):
        if hasattr(obj, 'user') and obj.user:
            first_name = getattr(obj.user, 'first_name', '')
            last_name = getattr(obj.user, 'last_name', '')
            return f"{first_name} {last_name}".strip() or "Noma'lum"
        return "Noma'lum"
    
    def get_specialization(self, obj):
        if hasattr(obj, 'specializations'):
            specs = obj.specializations.all()
            return [spec.name for spec in specs] if specs.exists() else []
        return []


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    selected_specialties_total = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient',
            'slot',
            'doctor',
            'clinic',
            'appointment_type',
            'status',
            'scheduled_date',
            'duration_minutes',
            'queue_position',
            'telegram_user_id',
            'telegram_confirmed_at',
            'telegram_reminder_sent_at',
            'reason',
            'notes',
            'patient_name',
            'selected_specialties',
            'selected_specialties_total',
            'consultation_fee',
            'is_paid',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name() if obj.patient and obj.patient.user else 'Bemor'

    def get_selected_specialties_total(self, obj):
        return sum(float(item.get('price', 0) or 0) for item in (obj.selected_specialties or []))


class OnlineAppointmentSerializer(serializers.Serializer):
    clinic = serializers.PrimaryKeyRelatedField(queryset=Clinic.objects.all())
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    slot_id = serializers.PrimaryKeyRelatedField(queryset=DoctorAvailability.objects.all(), required=False, allow_null=True)
    specialty_price_id = serializers.UUIDField(required=False, allow_null=True)
    specialty_price_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    patient_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    source = serializers.ChoiceField(choices=['online', 'reception'], default='online', required=False)
    reception_staff_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        full_name = str(attrs.get('full_name') or '').strip()
        first_name = str(attrs.get('first_name') or '').strip()
        last_name = str(attrs.get('last_name') or '').strip()
        if full_name and not first_name:
            parts = full_name.split()
            attrs['first_name'] = parts[0]
            attrs['last_name'] = ' '.join(parts[1:]) or '-'
        elif not first_name:
            raise serializers.ValidationError({'full_name': 'F.I.O yoki ism-familiya kiritilishi kerak.'})
        return attrs


class PublicTelegramBookingSerializer(serializers.Serializer):
    """Booking serializer for website booking without login + Telegram confirmation."""

    clinic = serializers.PrimaryKeyRelatedField(queryset=Clinic.objects.all())
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    specialty_price_id = serializers.UUIDField(required=False, allow_null=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    date = serializers.DateField()
    time = serializers.TimeField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        full_name = str(attrs.get('full_name') or '').strip()
        first_name = str(attrs.get('first_name') or '').strip()
        last_name = str(attrs.get('last_name') or '').strip()
        if not full_name and not first_name:
            raise serializers.ValidationError({'full_name': 'F.I.O yoki ism-familiya kiritilishi kerak.'})
        if not full_name:
            attrs['full_name'] = f'{first_name} {last_name}'.strip()
        return attrs


class MedicalRecordSerializer(serializers.ModelSerializer):
    doctor_details = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_specialization = serializers.SerializerMethodField()
    clinic_name = serializers.SerializerMethodField()
    clinic_details = serializers.SerializerMethodField()
    
    class Meta:
        model = MedicalRecord
        fields = [
            'id',
            'patient',
            'doctor',
            'doctor_details',
            'doctor_name',
            'doctor_specialization',
            'clinic',
            'clinic_name',
            'clinic_details',
            'appointment',
            'chief_complaint',
            'vital_signs',
            'examination_findings',
            'assessment',
            'plan',
            'attachment',
            'is_locked',
            'created_at',
            'updated_at',
        ]
    
    def get_doctor_details(self, obj):
        if obj.doctor:
            doctor = obj.doctor
            return {
                'id': doctor.id,
                'full_name': f"{doctor.user.first_name} {doctor.user.last_name}".strip() if doctor.user else "Noma'lum",
                'specializations': [spec.name for spec in doctor.specializations.all()] if doctor.specializations else []
            }
        return None
    
    def get_doctor_name(self, obj):
        # Arxivlangan ismni birinchi tekshir (doctor o'chirilgan bo'lsa)
        if obj.doctor_name:
            return obj.doctor_name
        # Agar arxiv bo'sh bo'lsa, hozirgi doctordan ol
        if obj.doctor and obj.doctor.user:
            return f"{obj.doctor.user.first_name} {obj.doctor.user.last_name}".strip()
        return "Noma'lum shifokor"
    
    def get_doctor_specialization(self, obj):
        if obj.doctor and obj.doctor.specializations:
            specs = obj.doctor.specializations.all()
            return [spec.name for spec in specs] if specs.exists() else []
        return []
    
    def get_clinic_name(self, obj):
        # Arxivlangan klinika nomini birinchi tekshir
        if obj.clinic_name:
            return obj.clinic_name
        # Agar arxiv bo'sh bo'lsa, hozirgi clinicdan ol
        if obj.clinic:
            return obj.clinic.name if hasattr(obj.clinic, 'name') else str(obj.clinic)
        return "Noma'lum klinika"
    
    def get_clinic_details(self, obj):
        if obj.clinic:
            clinic = obj.clinic
            return {
                'id': clinic.id,
                'name': clinic.name if hasattr(clinic, 'name') else str(clinic),
                'address': clinic.address if hasattr(clinic, 'address') else '',
                'phone': clinic.phone_number if hasattr(clinic, 'phone_number') else ''
            }
        return None


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = [
            'id',
            'medical_record',
            'diagnosis_code',
            'diagnosis_name',
            'certainty',
            'notes',
            'is_primary',
            'created_at',
        ]


class PrescriptionSerializer(serializers.ModelSerializer):
    doctor_details = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_specialization = serializers.SerializerMethodField()
    medicine_details = serializers.SerializerMethodField()
    clinic_name = serializers.SerializerMethodField()
    clinic_details = serializers.SerializerMethodField()
    
    # Note: Uses medical_record's archived doctor/clinic names
    
    class Meta:
        model = Prescription
        fields = [
            'id',
            'medical_record',
            'patient',
            'doctor',
            'doctor_details',
            'doctor_name',
            'doctor_specialization',
            'medicine',
            'medicine_details',
            'dosage',
            'frequency',
            'duration_days',
            'instructions',
            'quantity',
            'status',
            'issued_date',
            'expiry_date',
            'filled_at_pharmacy',
            'is_filled',
            'clinic_name',
            'clinic_details',
            'created_at',
            'updated_at',
        ]
    
    def get_doctor_details(self, obj):
        if obj.doctor:
            doctor = obj.doctor
            return {
                'id': doctor.id,
                'full_name': f"{doctor.user.first_name} {doctor.user.last_name}".strip() if doctor.user else "Noma'lum",
                'specializations': [spec.name for spec in doctor.specializations.all()] if doctor.specializations else []
            }
        return None
    
    def get_doctor_name(self, obj):
        # Arxivlangan ismni birinchi tekshir (doctor o'chirilgan bo'lsa)
        if obj.doctor_name:
            return obj.doctor_name
        # Agar arxiv bo'sh bo'lsa, hozirgi doctordan ol
        if obj.doctor and obj.doctor.user:
            return f"{obj.doctor.user.first_name} {obj.doctor.user.last_name}".strip()
        return "Noma'lum shifokor"
    
    def get_doctor_specialization(self, obj):
        if obj.doctor and obj.doctor.specializations:
            specs = obj.doctor.specializations.all()
            return [spec.name for spec in specs] if specs.exists() else []
        return []
    
    def get_medicine_details(self, obj):
        if obj.medicine:
            medicine = obj.medicine
            return {
                'id': medicine.id,
                'name': medicine.name,
                'category': medicine.category,
                'strength': getattr(medicine, 'strength', '')
            }
        return None
    
    def get_clinic_name(self, obj):
        # MedicalRecord'dan arxivlangan klinika nomini ol
        if obj.medical_record and obj.medical_record.clinic_name:
            return obj.medical_record.clinic_name
        # Agar arxiv bo'sh bo'lsa, hozirgi clinicdan ol
        if obj.medical_record and obj.medical_record.clinic:
            clinic = obj.medical_record.clinic
            return clinic.name if hasattr(clinic, 'name') else str(clinic)
        return "Noma'lum klinika"
    
    def get_clinic_details(self, obj):
        if obj.medical_record and obj.medical_record.clinic:
            clinic = obj.medical_record.clinic
            return {
                'id': clinic.id,
                'name': clinic.name if hasattr(clinic, 'name') else str(clinic),
                'address': clinic.address if hasattr(clinic, 'address') else '',
                'phone': clinic.phone_number if hasattr(clinic, 'phone_number') else ''
            }
        return None


class LabTestSerializer(serializers.ModelSerializer):
    doctor_details = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    test_type = serializers.CharField(source='test_code', required=False, allow_blank=True)
    
    class Meta:
        model = LabTest
        fields = [
            'id',
            'medical_record',
            'patient',
            'doctor',
            'doctor_details',
            'doctor_name',
            'test_name',
            'test_type',
            'status',
            'ordered_date',
            'scheduled_date',
            'completed_date',
            'results',
            'notes',
        ]
    
    def get_doctor_details(self, obj):
        if obj.doctor:
            doctor = obj.doctor
            return {
                'id': doctor.id,
                'full_name': f"{doctor.user.first_name} {doctor.user.last_name}".strip() if doctor.user else "Noma'lum",
                'specializations': [spec.name for spec in doctor.specializations.all()] if doctor.specializations else []
            }
        return None
    
    def get_doctor_name(self, obj):
        # Arxivlangan ismni birinchi tekshir (doctor o'chirilgan bo'lsa)
        if obj.doctor_name:
            return obj.doctor_name
        # Agar arxiv bo'sh bo'lsa, hozirgi doctordan ol
        if obj.doctor and obj.doctor.user:
            return f"{obj.doctor.user.first_name} {obj.doctor.user.last_name}".strip()
        return "Noma'lum shifokor"
