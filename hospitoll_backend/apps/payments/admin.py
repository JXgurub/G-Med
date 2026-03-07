# Admin configuration for payments app
from django.contrib import admin
from .models import Payment, Invoice


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'status', 'payment_method', 'paid_date', 'created_at')
    list_filter = ('status', 'payment_type', 'payment_method', 'created_at')
    search_fields = ('description', 'transaction_id', 'reference_number')
    ordering = ('-created_at',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'get_patient', 'net_amount', 'status', 'issued_date', 'due_date')
    list_filter = ('status', 'issued_date', 'due_date')
    search_fields = ('invoice_number', 'patient__user__email')
    ordering = ('-issued_date',)
    
    def get_patient(self, obj):
        if obj.patient:
            return obj.patient.user.get_full_name()
        return 'N/A'
    get_patient.short_description = 'Patient'
