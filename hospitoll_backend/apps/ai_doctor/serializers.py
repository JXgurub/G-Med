from rest_framework import serializers
from .models import AnalysisResult


class AnalysisUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    session_key = serializers.CharField(required=False, allow_blank=True, default='', max_length=64)

    def validate_file(self, value):
        if value.size > 20 * 1024 * 1024:  # 20MB
            raise serializers.ValidationError("Fayl hajmi 20MB dan oshmasligi kerak.")
        return value


class AnalysisResultSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisResult
        fields = [
            'id',
            'file_url',
            'file_type',
            'result_text',
            'language',
            'status',
            'created_at',
            'updated_at'
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None
