# Permissions module

from .custom_permissions import (
    IsAdministrator,
    IsClinic,
    IsDoctor,
    IsPatient,
    IsPharmacy,
    IsClinicOwner,
    IsPharmacyOwner,
    IsClinicAdmin,
    CanAccessMedicalRecord,
    IsActiveSubscription,
    CanCreateAppointment,
    ReadOnlyForPatients,
)

__all__ = [
    'IsAdministrator',
    'IsClinic',
    'IsDoctor',
    'IsPatient',
    'IsPharmacy',
    'IsClinicOwner',
    'IsPharmacyOwner',
    'IsClinicAdmin',
    'CanAccessMedicalRecord',
    'IsActiveSubscription',
    'CanCreateAppointment',
    'ReadOnlyForPatients',
]
