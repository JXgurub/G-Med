from django.utils import timezone
from rest_framework import serializers

from .models import PatientTreatmentPlan, PatientTreatmentStep


class PatientTreatmentStepSerializer(serializers.ModelSerializer):
    plan = serializers.PrimaryKeyRelatedField(
        queryset=PatientTreatmentPlan.objects.all(),
        required=True,
    )
    completed_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = PatientTreatmentStep
        fields = [
            'id',
            'plan',
            'title',
            'description',
            'due_date',
            'is_completed',
            'completed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_plan(self, plan):
        request = self.context.get('request')
        if not request or plan.patient.user_id != request.user.id:
            raise serializers.ValidationError('Bu reja sizga tegishli emas.')
        return plan

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Qadam nomini kiriting.')
        return value

    def create(self, validated_data):
        if validated_data.get('is_completed'):
            validated_data['completed_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'is_completed' in validated_data:
            validated_data['completed_at'] = (
                timezone.now() if validated_data['is_completed'] else None
            )
        return super().update(instance, validated_data)


class PatientTreatmentPlanSerializer(serializers.ModelSerializer):
    steps = PatientTreatmentStepSerializer(many=True, read_only=True)

    class Meta:
        model = PatientTreatmentPlan
        fields = [
            'id',
            'title',
            'summary',
            'start_date',
            'target_date',
            'status',
            'steps',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'steps', 'created_at', 'updated_at']

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Reja nomini kiriting.')
        return value

    def validate(self, attrs):
        start_date = attrs.get(
            'start_date',
            self.instance.start_date if self.instance else None,
        )
        target_date = attrs.get(
            'target_date',
            self.instance.target_date if self.instance else None,
        )
        if start_date and target_date and target_date < start_date:
            raise serializers.ValidationError({
                'target_date': 'Yakunlash sanasi boshlanish sanasidan oldin bo‘lishi mumkin emas.',
            })
        return attrs
