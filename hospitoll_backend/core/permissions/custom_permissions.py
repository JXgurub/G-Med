"""
Role-based permission classes for the Hospitoll platform.
Provides granular access control for different user roles.
"""

from rest_framework import permissions
from django.utils.translation import gettext_lazy as _


class IsAdministrator(permissions.BasePermission):
    """
    Permission for administrators only.
    """
    message = _("Faqat administratorlar bu amalni amalga oshira oladi.")
    
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_administrator or request.user.is_superuser)
        )


class IsClinic(permissions.BasePermission):
    """
    Permission for clinic users only.
    """
    message = _("Faqat klinika foydalanuvchilari bu amalni amalga oshira oladi.")
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_clinic


class IsDoctor(permissions.BasePermission):
    """
    Permission for doctor users only.
    """
    message = _("Faqat doktorlar bu amalni amalga oshira oladi.")
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_doctor


class IsPatient(permissions.BasePermission):
    """
    Permission for patient users only.
    """
    message = _("Faqat bemorlar bu amalni amalga oshira oladi.")
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_patient


class IsPharmacy(permissions.BasePermission):
    """
    Permission for pharmacy users only.
    """
    message = _("Faqat dorixona foydalanuvchilari bu amalni amalga oshira oladi.")
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_pharmacy


class IsClinicOwner(permissions.BasePermission):
    """
    Permission for clinic owner to access their own clinic.
    """
    message = _("Siz faqat o'z klinikangizni boshqara olasiz.")
    
    def has_object_permission(self, request, view, obj):
        # Check if the user is the owner of the clinic
        return request.user.is_authenticated and obj.owner == request.user


class IsPharmacyOwner(permissions.BasePermission):
    """
    Permission for pharmacy owner to access their own pharmacy.
    """
    message = _("Siz faqat o'z dorixonangizni boshqara olasiz.")
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and obj.owner == request.user


class IsClinicAdmin(permissions.BasePermission):
    """
    Permission for clinic staff to manage clinic resources.
    """
    message = _("Siz faqat o'z klinikangizning resurslarini boshqara olasiz.")
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # If user is administrator
        if request.user.is_administrator:
            return True
        
        # If clinic owner accessing their own clinic
        if request.user.is_clinic and hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        # If doctor checking their own clinic
        if request.user.is_doctor and hasattr(request.user, 'doctor'):
            return request.user.doctor.clinic == obj
        
        return False


class CanAccessMedicalRecord(permissions.BasePermission):
    """
    Permission to access medical records.
    - Doctors can access their own patients' records
    - Patients can access their own records
    - Administrators can access all records
    """
    message = _("Bu tibbiy yozuvga kira olmaysiz.")
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # Administrators can access everything
        if request.user.is_administrator:
            return True
        
        # Doctors can access their own patients' records
        if request.user.is_doctor and hasattr(request.user, 'doctor'):
            return obj.doctor == request.user.doctor or obj.patient in request.user.doctor.clinic.patients.all()
        
        # Patients can access their own records
        if request.user.is_patient and hasattr(request.user, 'patient'):
            return obj.patient == request.user.patient
        
        return False


class IsActiveSubscription(permissions.BasePermission):
    """
    Permission to check if clinic/pharmacy has active subscription.
    """
    message = _("Sizning obunangiz faol emas. Iltimos, obunani yangilang.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admins always have permission
        if request.user.is_administrator:
            return True
        
        # Check clinic subscription
        if request.user.is_clinic and hasattr(request.user, 'clinic'):
            clinic = request.user.clinic
            return clinic.is_active_status
        
        # Check pharmacy subscription
        if request.user.is_pharmacy and hasattr(request.user, 'pharmacy'):
            pharmacy = request.user.pharmacy
            return pharmacy.is_active_status
        
        # Doctors and patients don't need subscription check
        if request.user.is_doctor or request.user.is_patient:
            return True
        
        return False


class CanCreateAppointment(permissions.BasePermission):
    """
    Permission to create appointments.
    - Patients can create appointments for themselves
    - Doctors and clinics can create appointments
    """
    message = _("Siz randevular yarata olmaysiz.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Administrators, doctors, clinics can create appointments
        if request.user.is_administrator or request.user.is_doctor or request.user.is_clinic:
            return True
        
        # Patients can create appointments
        if request.user.is_patient:
            return True
        
        return False


class ReadOnlyForPatients(permissions.BasePermission):
    """
    Permission that allows patients read-only access.
    """
    message = _("Bemorlar faqat o'qish uchun ruxsat olgan.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_patient:
            return request.method in permissions.SAFE_METHODS
        
        return True
