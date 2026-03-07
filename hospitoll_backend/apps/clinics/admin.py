# Admin configuration for clinics app
from django.contrib import admin
from .models import Clinic, ClinicDepartment, ClinicService


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'status', 'is_verified', 'is_blocked', 'created_at')
    list_filter = ('status', 'is_verified', 'is_blocked', 'created_at')
    search_fields = ('name', 'registration_number', 'email')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'owner', 'description')
        }),
        ('Contact Information', {
            'fields': ('address', 'phone_number', 'email', 'website')
        }),
        ('Registration & Verification', {
            'fields': ('registration_number', 'license_document', 'is_verified')
        }),
        ('Status & Settings', {
            'fields': ('status', 'is_blocked')
        }),
        ('Media', {
            'fields': ('logo', 'banner_image')
        }),
        ('Metadata', {
            'fields': ('established_date', 'rating', 'total_ratings')
        }),
    )


@admin.register(ClinicDepartment)
class ClinicDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'clinic', 'is_active')
    list_filter = ('clinic', 'is_active')
    search_fields = ('name', 'clinic__name')


@admin.register(ClinicService)
class ClinicServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'clinic', 'department', 'price', 'is_active')
    list_filter = ('clinic', 'is_active')
    search_fields = ('name', 'clinic__name')
