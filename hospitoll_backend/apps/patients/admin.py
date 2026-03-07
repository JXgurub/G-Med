# Admin configuration for patients app
from django.contrib import admin
from .models import Patient, PatientMedicalHistory, PatientDoctorRating


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'gender', 'blood_type', 'is_active', 'created_at')
    list_filter = ('gender', 'blood_type', 'is_active', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    filter_horizontal = ('clinics',)
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Patient Name'
    
    def email(self, obj):
        return obj.user.email
    email.short_description = 'Email'


@admin.register(PatientMedicalHistory)
class PatientMedicalHistoryAdmin(admin.ModelAdmin):
    list_display = ('get_patient', 'condition', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('patient__user__email', 'condition')
    
    def get_patient(self, obj):
        return obj.patient.user.get_full_name()
    get_patient.short_description = 'Patient'


@admin.register(PatientDoctorRating)
class PatientDoctorRatingAdmin(admin.ModelAdmin):
    list_display = ('get_patient', 'get_doctor', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('patient__user__email', 'doctor__user__email')
    
    def get_patient(self, obj):
        return obj.patient.user.get_full_name()
    get_patient.short_description = 'Patient'
    
    def get_doctor(self, obj):
        return obj.doctor.user.get_full_name()
    get_doctor.short_description = 'Doctor'
