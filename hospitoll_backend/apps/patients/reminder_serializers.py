import re
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import PatientMedicationReminder
from .reminder_utils import next_scheduled_reminder_at


class PatientMedicationReminderSerializer(serializers.ModelSerializer):
    interval_hours = serializers.IntegerField(
        min_value=1,
        max_value=168,
        required=False,
        allow_null=True,
    )
    daily_times = serializers.ListField(
        child=serializers.CharField(max_length=5),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = PatientMedicationReminder
        fields = [
            'id',
            'medication_name',
            'interval_hours',
            'daily_times',
            'is_active',
            'next_reminder_at',
            'next_scheduled_reminder_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'next_reminder_at',
            'next_scheduled_reminder_at',
            'created_at',
            'updated_at',
        ]

    def validate_medication_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Dori nomini kiriting.')
        return value

    def validate_daily_times(self, value):
        if any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', item) for item in value):
            raise serializers.ValidationError('Vaqtni HH:MM formatida kiriting.')
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Bir xil vaqtni ikki marta kiritmang.')
        return sorted(value)

    def validate(self, attrs):
        interval_hours = attrs.get(
            'interval_hours',
            self.instance.interval_hours if self.instance else None,
        )
        daily_times = attrs.get(
            'daily_times',
            self.instance.daily_times if self.instance else [],
        )

        if (interval_hours is None) == (not daily_times):
            raise serializers.ValidationError(
                'Eslatma uchun interval yoki aniq vaqtlarni tanlang — faqat bittasini.'
            )
        return attrs

    def create(self, validated_data):
        interval_hours = validated_data.get('interval_hours')
        validated_data['next_reminder_at'] = (
            timezone.now() + timedelta(hours=interval_hours)
            if interval_hours is not None
            else None
        )
        validated_data['next_scheduled_reminder_at'] = next_scheduled_reminder_at(
            validated_data.get('daily_times', []),
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        previous_interval = instance.interval_hours
        previous_daily_times = instance.daily_times
        was_active = instance.is_active
        instance = super().update(instance, validated_data)
        if not instance.is_active:
            instance.pending_dose_at = None
            instance.next_nudge_at = None
            instance.acknowledgement_token = None
            instance.save(update_fields=[
                'pending_dose_at',
                'next_nudge_at',
                'acknowledgement_token',
                'updated_at',
            ])
        elif (
            instance.interval_hours != previous_interval
            or instance.daily_times != previous_daily_times
            or not was_active
        ):
            if instance.interval_hours is None:
                instance.next_reminder_at = None
            elif instance.interval_hours != previous_interval or not was_active:
                instance.next_reminder_at = timezone.now() + timedelta(hours=instance.interval_hours)
            instance.next_scheduled_reminder_at = next_scheduled_reminder_at(
                instance.daily_times,
            )
            instance.pending_dose_at = None
            instance.next_nudge_at = None
            instance.acknowledgement_token = None
            instance.save(update_fields=[
                'next_reminder_at',
                'next_scheduled_reminder_at',
                'pending_dose_at',
                'next_nudge_at',
                'acknowledgement_token',
                'updated_at',
            ])
        return instance
