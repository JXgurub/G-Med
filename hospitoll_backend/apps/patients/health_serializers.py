from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from . import health_thresholds as thresholds
from .models import PatientHealthReading, PatientLiverJournalEntry


LIVER_METRICS = {
    PatientHealthReading.Metric.LIVER_ALT,
    PatientHealthReading.Metric.LIVER_AST,
    PatientHealthReading.Metric.LIVER_BILIRUBIN,
    PatientHealthReading.Metric.LIVER_ALBUMIN,
    PatientHealthReading.Metric.LIVER_GGT,
    PatientHealthReading.Metric.LIVER_VIRAL_LOAD,
}


class PatientHealthReadingSerializer(serializers.ModelSerializer):
    glucose_mmol = serializers.DecimalField(
        max_digits=4,
        decimal_places=1,
        required=False,
        allow_null=True,
        min_value=Decimal('0.5'),
        max_value=Decimal('60'),
    )
    systolic = serializers.IntegerField(required=False, allow_null=True, min_value=50, max_value=300)
    diastolic = serializers.IntegerField(required=False, allow_null=True, min_value=30, max_value=200)
    measured_at = serializers.DateTimeField(required=False)
    value = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        required=False,
        allow_null=True,
        min_value=Decimal('0'),
    )
    unit = serializers.CharField(required=False, allow_blank=True, max_length=30)
    reference_min = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True, min_value=Decimal('0'),
    )
    reference_max = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True, min_value=Decimal('0'),
    )

    class Meta:
        model = PatientHealthReading
        fields = [
            'id',
            'metric',
            'systolic',
            'diastolic',
            'glucose_mmol',
            'glucose_context',
            'value',
            'unit',
            'reference_min',
            'reference_max',
            'measured_at',
            'note',
            'severity',
            'alert_reason',
            'share_with_care_team',
            'created_at',
        ]
        read_only_fields = ['id', 'severity', 'alert_reason', 'created_at']

    def validate_measured_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError('O‘lchov vaqti kelajakda bo‘lishi mumkin emas.')
        return value

    def validate_note(self, value):
        return value.strip()

    def validate(self, attrs):
        metric = attrs['metric']
        if metric == PatientHealthReading.Metric.BLOOD_PRESSURE:
            systolic = attrs.get('systolic')
            diastolic = attrs.get('diastolic')
            if systolic is None or diastolic is None:
                raise serializers.ValidationError(
                    {'systolic': 'Yuqori va pastki bosimni kiriting.'}
                )
            if systolic <= diastolic:
                raise serializers.ValidationError(
                    {'systolic': 'Yuqori bosim pastki bosimdan katta bo‘lishi kerak.'}
                )
            attrs['glucose_mmol'] = None
            attrs['glucose_context'] = ''
        elif metric == PatientHealthReading.Metric.BLOOD_GLUCOSE:
            if attrs.get('glucose_mmol') is None:
                raise serializers.ValidationError({'glucose_mmol': 'Qon qandi qiymatini kiriting.'})
            if not attrs.get('glucose_context'):
                raise serializers.ValidationError({'glucose_context': 'O‘lchov vaqtini tanlang.'})
            attrs['systolic'] = None
            attrs['diastolic'] = None
        elif metric in LIVER_METRICS:
            if attrs.get('value') is None:
                raise serializers.ValidationError({'value': 'Tahlil natijasini kiriting.'})
            if not attrs.get('unit', '').strip():
                raise serializers.ValidationError({'unit': 'Tahlil birligini kiriting.'})
            reference_min = attrs.get('reference_min')
            reference_max = attrs.get('reference_max')
            if reference_min is None and reference_max is None:
                raise serializers.ValidationError(
                    {'reference_max': 'Laboratoriya blankasidagi me’yor oralig‘ini kiriting.'}
                )
            if reference_min is not None and reference_max is not None and reference_min > reference_max:
                raise serializers.ValidationError(
                    {'reference_max': 'Yuqori me’yor pastki me’yordan kichik bo‘lishi mumkin emas.'}
                )
            attrs['systolic'] = None
            attrs['diastolic'] = None
            attrs['glucose_mmol'] = None
            attrs['glucose_context'] = ''
        else:
            raise serializers.ValidationError({'metric': 'Ko‘rsatkich turi tanilmadi.'})
        return attrs

    def create(self, validated_data):
        validated_data.setdefault('measured_at', timezone.now())
        if validated_data['metric'] == PatientHealthReading.Metric.BLOOD_PRESSURE:
            severity, reason = thresholds.evaluate_blood_pressure(
                validated_data['systolic'],
                validated_data['diastolic'],
            )
        elif validated_data['metric'] == PatientHealthReading.Metric.BLOOD_GLUCOSE:
            severity, reason = thresholds.evaluate_blood_glucose(
                validated_data['glucose_mmol'],
                validated_data['glucose_context'],
            )
        else:
            severity, reason = thresholds.evaluate_liver_result(
                validated_data['value'],
                validated_data.get('reference_min'),
                validated_data.get('reference_max'),
            )
        validated_data['severity'] = severity
        validated_data['alert_reason'] = reason
        return super().create(validated_data)


class PatientLiverJournalEntrySerializer(serializers.ModelSerializer):
    symptoms = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ('jaundice', 'Sariqlik'),
            ('abdominal_swelling', 'Qorin shishishi'),
            ('fatigue', 'Charchoq'),
            ('itching', 'Qichishish'),
            ('dark_urine', 'Qorong‘i siydik'),
            ('weight_change', 'Vazn o‘zgarishi'),
            ('bloody_vomit', 'Qon qusish'),
            ('black_stool', 'Qora najas'),
            ('confusion', 'Chalkashlik'),
        ]),
        required=False,
        allow_empty=True,
    )
    recorded_at = serializers.DateTimeField(required=False)

    class Meta:
        model = PatientLiverJournalEntry
        fields = [
            'id',
            'symptoms',
            'weight_kg',
            'abdominal_circumference_cm',
            'salt_grams',
            'fluid_ml',
            'note',
            'recorded_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        if not any(attrs.get(field) is not None for field in (
            'weight_kg', 'abdominal_circumference_cm', 'salt_grams', 'fluid_ml',
        )) and not attrs.get('symptoms') and not attrs.get('note', '').strip():
            raise serializers.ValidationError('Belgi, o‘lchov yoki izoh kiriting.')
        return attrs

    def validate_recorded_at(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError('Yozuv vaqti kelajakda bo‘lishi mumkin emas.')
        return value

    def validate_note(self, value):
        return value.strip()


class HealthAlertSerializer(serializers.ModelSerializer):
    patient_id = serializers.UUIDField(source='patient.id', read_only=True)
    patient_name = serializers.SerializerMethodField()
    patient_number = serializers.CharField(source='patient.patient_number', read_only=True)
    patient_phone = serializers.SerializerMethodField()
    is_reviewed = serializers.SerializerMethodField()

    class Meta:
        model = PatientHealthReading
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'patient_number',
            'patient_phone',
            'metric',
            'systolic',
            'diastolic',
            'glucose_mmol',
            'glucose_context',
            'value',
            'unit',
            'reference_min',
            'reference_max',
            'measured_at',
            'note',
            'severity',
            'alert_reason',
            'is_reviewed',
            'reviewed_at',
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name() or obj.patient.user.get_username()

    def get_patient_phone(self, obj):
        return obj.patient.phone_number or getattr(obj.patient.user, 'phone_number', '') or ''

    def get_is_reviewed(self, obj):
        return obj.reviewed_at is not None
