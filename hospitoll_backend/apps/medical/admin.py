# Admin configuration for medical app
from django.contrib import admin
from .models import Appointment, MedicalRecord, Diagnosis, Prescription, LabTest


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'scheduled_date', 'status', 'is_paid', 'created_at')
    list_filter = ('status', 'appointment_type', 'is_paid', 'scheduled_date')
    search_fields = ('patient__user__email', 'doctor__user__email')
    ordering = ('-scheduled_date',)


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('get_patient', 'get_doctor', 'is_locked', 'created_at')
    list_filter = ('is_locked', 'created_at')
    search_fields = ('patient__user__email', 'doctor__user__email')
    
    def get_patient(self, obj):
        return obj.patient.user.get_full_name()
    get_patient.short_description = 'Patient'
    
    def get_doctor(self, obj):
        return obj.doctor.user.get_full_name()
    get_doctor.short_description = 'Doctor'


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ('diagnosis_name', 'diagnosis_code', 'certainty', 'is_primary', 'created_at')
    list_filter = ('certainty', 'is_primary', 'created_at')
    search_fields = ('diagnosis_name', 'diagnosis_code')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('get_medicine', 'get_patient', 'status', 'is_filled', 'issued_date')
    list_filter = ('status', 'is_filled', 'issued_date')
    search_fields = ('patient__user__email', 'medicine__name')
    
    def get_patient(self, obj):
        return obj.patient.user.get_full_name()
    get_patient.short_description = 'Patient'
    
    def get_medicine(self, obj):
        return obj.medicine.name if obj.medicine else 'N/A'
    get_medicine.short_description = 'Medicine'


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ('test_name', 'get_patient', 'status', 'ordered_date', 'completed_date')
    list_filter = ('status', 'ordered_date')
    search_fields = ('patient__user__email', 'test_name', 'test_code')
    
    def get_patient(self, obj):
        return obj.patient.user.get_full_name()
    get_patient.short_description = 'Patient'
