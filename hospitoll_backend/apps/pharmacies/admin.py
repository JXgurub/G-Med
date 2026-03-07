# Admin configuration for pharmacies app
from django.contrib import admin
from .models import Pharmacy, Medicine, PharmacyMarchandise


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
