from rest_framework import serializers

from .models import ContactLead, HomeContactSettings, SystemAlert


class HomeContactSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeContactSettings
        fields = [
            'id',
            'text',
            'telegram_link',
            'phone_number',
            'instagram_link',
            'email',
            'email_display',
            'image',
            'updated_at',
        ]


class ContactLeadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactLead
        fields = ['id', 'name', 'phone_number', 'email', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        phone = (attrs.get('phone_number') or '').strip()
        email = (attrs.get('email') or '').strip()
        message = (attrs.get('message') or '').strip()

        if not phone and not email:
            raise serializers.ValidationError("Telefon yoki email kiritilishi kerak.")
        if not message:
            raise serializers.ValidationError("Xabar (message) bo'sh bo'lmasin.")
        return attrs


class ContactLeadAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactLead
        fields = ['id', 'name', 'phone_number', 'email', 'message', 'is_read', 'read_at', 'created_at']


class SystemAlertAdminSerializer(serializers.ModelSerializer):
    resolved_by_email = serializers.EmailField(source='resolved_by.email', read_only=True)

    class Meta:
        model = SystemAlert
        fields = [
            'id',
            'alert_type',
            'message',
            'severity',
            'context',
            'traceback',
            'is_resolved',
            'resolved_at',
            'resolved_by',
            'resolved_by_email',
            'created_at',
        ]
        read_only_fields = fields
