# Admin configuration for pharmacies app
from django.contrib import admin
from .models import (
    Pharmacy,
    Medicine,
    PharmacyMarchandise,
    PharmacyPosDevice,
    PharmacySale,
    PharmacySaleLine,
)


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'status', 'is_verified', 'is_blocked', 'created_at')
    list_filter = ('status', 'is_verified', 'is_blocked', 'created_at')
    search_fields = ('name', 'registration_number', 'email')
    ordering = ('-created_at',)


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'generic_name', 'dosage_form', 'strength', 'is_prescription_required', 'is_active')
    list_filter = ('is_prescription_required', 'is_active')
    search_fields = ('name', 'generic_name', 'atc_code')


@admin.register(PharmacyMarchandise)
class PharmacyMarchandiseAdmin(admin.ModelAdmin):
    list_display = ('get_medicine', 'get_pharmacy', 'batch_number', 'expiry_date', 'quantity_in_stock', 'is_available')
    list_filter = ('pharmacy', 'is_available', 'expiry_date')
    search_fields = ('medicine__name', 'pharmacy__name', 'batch_number')
    
    def get_medicine(self, obj):
        return obj.medicine.name
    get_medicine.short_description = 'Medicine'
    
    def get_pharmacy(self, obj):
        return obj.pharmacy.name
    get_pharmacy.short_description = 'Pharmacy'


@admin.register(PharmacyPosDevice)
class PharmacyPosDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'pharmacy', 'is_active', 'client_id', 'created_at', 'last_seen_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'pharmacy__name', 'client_id')
    readonly_fields = ('activation_code_hash', 'client_id', 'created_at', 'activated_at', 'last_seen_at')


class PharmacySaleLineInline(admin.TabularInline):
    model = PharmacySaleLine
    extra = 0
    can_delete = False
    readonly_fields = (
        'medicine_name',
        'quantity',
        'unit_price',
        'line_total',
        'stock_shortfall',
        'stock_mismatch',
        'inventory',
        'medicine',
    )


@admin.register(PharmacySale)
class PharmacySaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'pharmacy', 'device', 'sold_at', 'total', 'has_stock_discrepancy', 'synced_at')
    list_filter = ('has_stock_discrepancy', 'pharmacy', 'sold_at')
    search_fields = ('id', 'pharmacy__name', 'device__name')
    readonly_fields = ('id', 'pharmacy', 'device', 'sold_at', 'total', 'synced_at', 'has_stock_discrepancy')
    inlines = (PharmacySaleLineInline,)
