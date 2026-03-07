"""
DoctorSpecialization ViewSet for managing doctor specialties and pricing
"""
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import QuerySet

from .models import DoctorSpecialization, Doctor
from .serializers import DoctorSpecializationSerializer


class DoctorSpecializationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing doctor specializations and their prices
    Doctors can manage their own specializations and prices
    """
    queryset = DoctorSpecialization.objects.select_related('doctor', 'specialization').all()
    serializer_class = DoctorSpecializationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['doctor', 'specialization', 'is_active']

    def get_queryset(self) -> QuerySet:  # type: ignore
        """
        Doctors can only see/edit their own specializations
        Clinic owners can see all specializations for their clinic's doctors
        """
        user = self.request.user
        queryset = DoctorSpecialization.objects.select_related('doctor', 'specialization')
        
        # If user is a doctor, show only their specializations
        if hasattr(user, 'doctor') and user.doctor is not None:  # type: ignore
            queryset = queryset.filter(doctor=user.doctor)  # type: ignore
        
        # If user is clinic owner, show specializations for their clinic's doctors
        elif hasattr(user, 'clinic') and user.clinic is not None:  # type: ignore
            queryset = queryset.filter(doctor__clinic=user.clinic)  # type: ignore
        
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new doctor specialization with pricing"""
        # If doctor is adding their own specialization, auto-fill the doctor field
        if hasattr(request.user, 'doctor'):
            request.data['doctor'] = request.user.doctor.id
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Update doctor specialization (mainly to update price)"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Prevent changing doctor field
        if 'doctor' in request.data:
            del request.data['doctor']
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_specializations(self, request):
        """Get current doctor's specializations with prices"""
        if not hasattr(request.user, 'doctor'):
            return Response({'detail': 'Siz doktor emassiz.'}, status=status.HTTP_403_FORBIDDEN)
        
        doctor = request.user.doctor
        specializations = DoctorSpecialization.objects.filter(
            doctor=doctor,
            is_active=True
        ).select_related('specialization')
        
        serializer = self.get_serializer(specializations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_clinic(self, request):
        """Get all specializations for clinic's doctors"""
        clinic_id = request.query_params.get('clinic_id')
        if not clinic_id:
            return Response({'detail': 'clinic_id parametri kerak.'}, status=status.HTTP_400_BAD_REQUEST)
        
        specializations = DoctorSpecialization.objects.filter(
            doctor__clinic_id=clinic_id,
            is_active=True
        ).select_related('specialization', 'doctor')
        
        serializer = self.get_serializer(specializations, many=True)
        return Response(serializer.data)
