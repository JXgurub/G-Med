# Admin configuration for doctors app
from django.contrib import admin
from .models import Specialization, Doctor, DoctorAvailability


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_clinic', 'license_number', 'is_verified', 'rating', 'created_at')
    list_filter = ('clinic', 'is_verified', 'is_active', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'license_number')
    filter_horizontal = ('specializations',)
    ordering = ('-created_at',)
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Doctor Name'
    
    def get_clinic(self, obj):
        return obj.clinic.name
    get_clinic.short_description = 'Clinic'


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('get_doctor', 'date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'date')
    search_fields = ('doctor__user__email', 'doctor__user__first_name')
    
    def get_doctor(self, obj):
        return obj.doctor.user.get_full_name()
    get_doctor.short_description = 'Doctor'
