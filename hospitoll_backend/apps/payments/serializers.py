"""
Serializers for payments and invoices
"""

from rest_framework import serializers
from .models import Payment, Invoice


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    clinic_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_type',
            'status',
            'clinic',
            'clinic_name',
            'pharmacy',
            'patient',
            'patient_name',
            'appointment',
            'description',
            'amount',
            'payment_method',
            'transaction_id',
            'reference_number',
            'notes',
            'paid_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'transaction_id', 'created_at', 'updated_at']
    
    def get_clinic_name(self, obj):
        """Get clinic name"""
        return obj.clinic.name if obj.clinic else None
    
    def get_patient_name(self, obj):
        """Get patient name"""
        if obj.patient and obj.patient.user:
            return obj.patient.user.get_full_name()
        return None


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model"""
    
    clinic_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'clinic',
            'clinic_name',
            'pharmacy',
            'patient',
            'patient_name',
            'status',
            'total_amount',
            'tax_amount',
            'discount_amount',
            'net_amount',
            'paid_amount',
            'remaining_amount',
            'payment_terms',
            'due_date',
            'issued_date',
            'paid_date',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at']
    
    def get_clinic_name(self, obj):
        """Get clinic name"""
        return obj.clinic.name if obj.clinic else None
    
    def get_patient_name(self, obj):
        """Get patient name"""
        if obj.patient and obj.patient.user:
            return obj.patient.user.get_full_name()
        return None
    
    def get_remaining_amount(self, obj):
        """Calculate remaining amount"""
        return float(obj.net_amount - obj.paid_amount)
