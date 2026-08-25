from rest_framework import serializers

from .models import PrinterDevice, PrintJob


class PrinterDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrinterDevice
        fields = [
            'id',
            'clinic',
            'reception_room',
            'device_name',
            'printer_name',
            'device_token',
            'status',
            'last_seen',
            'created_at',
            'updated_at',
        ]


class PrintJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrintJob
        fields = [
            'id',
            'clinic',
            'reception_room',
            'printer_device',
            'appointment',
            'created_by',
            'status',
            'payload',
            'error_message',
            'created_at',
            'printed_at',
        ]
