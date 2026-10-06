from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import PatientMedicationReminder


class PatientMedicationReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientMedicationReminder
        fields = [
            'id',
            'medication_name',
            'interval_hours',
            'is_active',
            'next_reminder_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'next_reminder_at', 'created_at', 'updated_at']

    def validate_medication_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Dori nomini kiriting.')
        return value

    def create(self, validated_data):
        interval_hours = validated_data['interval_hours']
        validated_data['next_reminder_at'] = timezone.now() + timedelta(hours=interval_hours)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        previous_interval = instance.interval_hours
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
        elif instance.interval_hours != previous_interval or not was_active:
            instance.next_reminder_at = timezone.now() + timedelta(hours=instance.interval_hours)
            instance.pending_dose_at = None
            instance.next_nudge_at = None
            instance.acknowledgement_token = None
            instance.save(update_fields=[
                'next_reminder_at',
                'pending_dose_at',
                'next_nudge_at',
                'acknowledgement_token',
                'updated_at',
            ])
        return instance
