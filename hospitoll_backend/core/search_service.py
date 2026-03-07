"""
Full-Text Search Service
Implements PostgreSQL full-text search for doctors, clinics, patients, medical records
"""

from django.db.models import Q, F, Value, CharField
from django.db.models.functions import Concat, Cast
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.aggregates import ArrayAgg
from rest_framework.exceptions import ValidationError
from typing import List, Dict, Optional, Tuple, Union
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class FullTextSearchService:
    """
    Full-text search service for Hospitoll
    Supports searching across doctors, clinics, patients, appointments, and medical records
    """
    
    # Search models mapping
    SEARCH_MODELS = {
        'doctors': 'apps.doctors.models.Doctor',
        'clinics': 'apps.clinics.models.Clinic',
        'patients': 'apps.patients.models.Patient',
        'appointments': 'apps.medical.models.Appointment',
        'medical_records': 'apps.medical.models.MedicalRecord',
        'pharmacies': 'apps.pharmacies.models.Pharmacy',
    }
    
    def __init__(self):
        self.min_query_length = 3  # Minimum search query length
        self.max_results = 100  # Maximum results per model
    
    def search(self, query: str, models: Optional[List[str]] = None, limit: int = 20) -> Dict:
        """
        Perform full-text search across specified models
        
        Args:
            query: Search query string
            models: List of model names to search in. If None, search all
            limit: Maximum results to return per model
            
        Returns:
            dict: Structured search results
        """
        try:
            # Validate query
            if not query or len(query.strip()) < self.min_query_length:
                raise ValidationError(f"Query must be at least {self.min_query_length} characters")
            
            query = query.strip()
            
            # Determine models to search
            search_models = models if models else list(self.SEARCH_MODELS.keys())
            
            results = {}
            
            for model_name in search_models:
                try:
                    if model_name == 'doctors':
                        results['doctors'] = self._search_doctors(query, limit)
                    elif model_name == 'clinics':
                        results['clinics'] = self._search_clinics(query, limit)
                    elif model_name == 'patients':
                        results['patients'] = self._search_patients(query, limit)
                    elif model_name == 'appointments':
                        results['appointments'] = self._search_appointments(query, limit)
                    elif model_name == 'medical_records':
                        results['medical_records'] = self._search_medical_records(query, limit)
                    elif model_name == 'pharmacies':
                        results['pharmacies'] = self._search_pharmacies(query, limit)
                except Exception as e:
                    logger.error(f"Error searching {model_name}: {str(e)}")
                    results[model_name] = {'items': [], 'error': str(e)}
            
            return {
                'query': query,
                'results': results,
                'total_count': sum(len(r.get('items', [])) for r in results.values())
            }
        
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise
    
    def _search_doctors(self, query: str, limit: int) -> Dict:
        """Search doctors by name, specialty, qualification"""
        try:
            from apps.doctors.models import Doctor
            
            # Create search vector
            search_vector = (
                SearchVector('first_name', weight='A') +
                SearchVector('last_name', weight='A') +
                SearchVector('patronymic', weight='B') +
                SearchVector('specialty__name', weight='A') +
                SearchVector('qualification', weight='C') +
                SearchVector('bio', weight='D')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            doctors = Doctor.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_doctor_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for doctor in doctors:
                items.append({
                    'id': doctor.id,
                    'type': 'doctor',
                    'name': doctor.user.get_full_name() or doctor.user.username,
                    'specialty': doctor.specializations_display,
                    'clinic': doctor.clinic.name if doctor.clinic else 'N/A',
                    'bio': doctor.bio,
                    'avatar': str(doctor.profile_image.url) if doctor.profile_image else None,
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching doctors: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    def _search_clinics(self, query: str, limit: int) -> Dict:
        """Search clinics by name, location, specialty"""
        try:
            from apps.clinics.models import Clinic
            
            search_vector = (
                SearchVector('name', weight='A') +
                SearchVector('location', weight='B') +
                SearchVector('description', weight='C') +
                SearchVector('phone', weight='D')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            clinics = Clinic.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_clinic_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for clinic in clinics:
                items.append({
                    'id': clinic.id,
                    'type': 'clinic',
                    'name': clinic.name,
                    'location': clinic.address,
                    'phone': clinic.phone_number,
                    'email': clinic.email,
                    'doctors_count': clinic.doctors.count() if hasattr(clinic, 'doctors') else 0,  # type: ignore[attr-defined]
                    'rating': getattr(clinic, 'rating', None),
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching clinics: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    def _search_patients(self, query: str, limit: int) -> Dict:
        """Search patients by name, phone, email"""
        try:
            from apps.patients.models import Patient
            
            search_vector = (
                SearchVector('first_name', weight='A') +
                SearchVector('last_name', weight='A') +
                SearchVector('phone_number', weight='B') +
                SearchVector('email', weight='B') +
                SearchVector('passport_number', weight='C')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            patients = Patient.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_patient_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for patient in patients:
                items.append({
                    'id': patient.id,
                    'type': 'patient',
                    'name': patient.user.get_full_name() or patient.user.username,
                    'phone': patient.phone_number,
                    'email': patient.user.email,
                    'birth_date': patient.date_of_birth,
                    'blood_type': getattr(patient, 'blood_type', None),
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    def _search_appointments(self, query: str, limit: int) -> Dict:
        """Search appointments by doctor, patient, status"""
        try:
            from apps.medical.models import Appointment
            
            search_vector = (
                SearchVector('doctor__first_name', weight='A') +
                SearchVector('doctor__last_name', weight='A') +
                SearchVector('patient__first_name', weight='A') +
                SearchVector('patient__last_name', weight='A') +
                SearchVector('status', weight='B') +
                SearchVector('notes', weight='C')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            appointments = Appointment.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_appointment_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for appt in appointments:
                items.append({
                    'id': appt.id,
                    'type': 'appointment',
                    'doctor': appt.doctor.user.get_full_name() if appt.doctor else appt.doctor_name,
                    'patient': appt.patient.user.get_full_name() if appt.patient else 'N/A',
                    'date': appt.scheduled_date,
                    'status': appt.status,
                    'clinic': appt.clinic.name if appt.clinic else appt.clinic_name,
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching appointments: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    def _search_medical_records(self, query: str, limit: int) -> Dict:
        """Search medical records by diagnosis, symptoms, notes"""
        try:
            from apps.medical.models import MedicalRecord
            
            search_vector = (
                SearchVector('diagnosis', weight='A') +
                SearchVector('symptoms', weight='B') +
                SearchVector('treatment_plan', weight='C') +
                SearchVector('notes', weight='D')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            records = MedicalRecord.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_medical_record_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for record in records:
                items.append({
                    'id': record.id,
                    'type': 'medical_record',
                    'patient': record.patient.user.get_full_name() if record.patient else 'N/A',
                    'complaint': record.chief_complaint,
                    'assessment': record.assessment,
                    'date': record.created_at,
                    'doctor': record.doctor.user.get_full_name() if record.doctor else record.doctor_name,
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching medical records: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    def _search_pharmacies(self, query: str, limit: int) -> Dict:
        """Search pharmacies by name, location"""
        try:
            from apps.pharmacies.models import Pharmacy
            
            search_vector = (
                SearchVector('name', weight='A') +
                SearchVector('location', weight='B') +
                SearchVector('phone_number', weight='C')
            )
            
            search_query = SearchQuery(query, search_type='websearch')
            
            pharmacies = Pharmacy.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                Q(search=search_query) | self._get_pharmacy_fallback_query(query)
            ).order_by('-rank')[:limit]
            
            items = []
            for pharmacy in pharmacies:
                items.append({
                    'id': pharmacy.id,
                    'type': 'pharmacy',
                    'name': pharmacy.name,
                    'location': pharmacy.address,
                    'phone': pharmacy.phone_number,
                    'email': getattr(pharmacy, 'email', None),
                })
            
            return {'items': items, 'count': len(items)}
        
        except Exception as e:
            logger.error(f"Error searching pharmacies: {str(e)}")
            return {'items': [], 'count': 0, 'error': str(e)}
    
    # Fallback query methods for non-PostgreSQL environments
    def _get_doctor_fallback_query(self, query: str) -> Q:
        """Fallback query for doctor search when FTS not available"""
        return Q(first_name__icontains=query) | \
               Q(last_name__icontains=query) | \
               Q(specialty__name__icontains=query) | \
               Q(qualification__icontains=query)
    
    def _get_clinic_fallback_query(self, query: str) -> Q:
        """Fallback query for clinic search"""
        return Q(name__icontains=query) | Q(location__icontains=query)
    
    def _get_patient_fallback_query(self, query: str) -> Q:
        """Fallback query for patient search"""
        return Q(first_name__icontains=query) | \
               Q(last_name__icontains=query) | \
               Q(phone_number__icontains=query) | \
               Q(email__icontains=query)
    
    def _get_appointment_fallback_query(self, query: str) -> Q:
        """Fallback query for appointment search"""
        return Q(doctor__first_name__icontains=query) | \
               Q(doctor__last_name__icontains=query) | \
               Q(patient__first_name__icontains=query) | \
               Q(patient__last_name__icontains=query) | \
               Q(status__icontains=query)
    
    def _get_medical_record_fallback_query(self, query: str) -> Q:
        """Fallback query for medical record search"""
        return Q(diagnosis__icontains=query) | \
               Q(symptoms__icontains=query) | \
               Q(treatment_plan__icontains=query) | \
               Q(notes__icontains=query)
    
    def _get_pharmacy_fallback_query(self, query: str) -> Q:
        """Fallback query for pharmacy search"""
        return Q(name__icontains=query) | Q(location__icontains=query)
    
    def search_doctors_by_specialty(self, specialty_id: Union[int, str, UUID]):
        """
        Search doctors by specialty
        
        Args:
            specialty_id: Specialty ID
            
        Returns:
            QuerySet of doctors in that specialty
        """
        from apps.doctors.models import Doctor
        
        try:
            doctors = Doctor.objects.filter(
                specializations__id=specialty_id,
                is_active=True
            ).distinct()
            
            return doctors
        
        except Exception as e:
            logger.error(f"Error searching by specialty: {str(e)}")
            return Doctor.objects.none()
    
    def search_available_doctors(self, clinic_id: Union[int, str, UUID], date: Optional[str] = None):
        """
        Search available doctors in clinic
        
        Args:
            clinic_id: Clinic ID (int, str, or UUID)
            date: Optional specific date (YYYY-MM-DD)
            
        Returns:
            QuerySet of available doctors
        """
        try:
            from apps.doctors.models import Doctor
            
            doctors = Doctor.objects.filter(
                clinic_id=clinic_id,
                is_active=True
            )
            
            return doctors
        
        except Exception as e:
            logger.error(f"Error searching available doctors: {str(e)}")
            from apps.doctors.models import Doctor
            return Doctor.objects.none()
    
    def get_search_suggestions(self, query: str, model: Optional[str] = None) -> List[str]:
        """
        Get search suggestions based on partial query
        
        Args:
            query: Partial query string
            model: Optional model to limit suggestions to
            
        Returns:
            List of suggestion strings
        """
        try:
            suggestions = []
            
            if len(query) < 2:
                return suggestions
            
            # Doctor suggestions
            if not model or model == 'doctors':
                from apps.doctors.models import Doctor
                names = Doctor.objects.filter(
                    Q(first_name__istartswith=query) |
                    Q(last_name__istartswith=query)
                ).values_list('first_name', 'last_name').distinct()[:5]
                suggestions.extend([f"{n[0]} {n[1]}" for n in names])
            
            # Clinic suggestions
            if not model or model == 'clinics':
                from apps.clinics.models import Clinic
                names = Clinic.objects.filter(
                    name__istartswith=query
                ).values_list('name', flat=True).distinct()[:5]
                suggestions.extend(names)
            
            # Specialty suggestions
            if not model or model == 'specialties':
                from apps.doctors.models import Specialization
                names = Specialization.objects.filter(
                    name__istartswith=query
                ).values_list('name', flat=True).distinct()[:5]
                suggestions.extend(names)
            
            return list(set(suggestions))[:10]  # Remove duplicates and limit
        
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}")
            return []
