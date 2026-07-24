from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q

from .models import Patient
from .serializers import PatientSerializer, PatientCreateSerializer


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.select_related('user').all()
    filterset_fields = ['gender', 'city', 'is_active']

    def get_queryset(self):
        qs = super().get_queryset()

        query = str(self.request.query_params.get('q') or '').strip()
        if query:
            qs = qs.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(phone_number__icontains=query)
                | Q(user__phone_number__icontains=query)
            )

        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        if self.action == 'my':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return PatientCreateSerializer
        return PatientSerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_patient:
            return Response({'detail': 'Bemor topilmadi.'}, status=404)
        patient = Patient.objects.filter(user=request.user).first()
        if not patient:
            return Response({'detail': 'Bemor topilmadi.'}, status=404)
        serializer = PatientSerializer(patient)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_password(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat yo‘q.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not (request.user.is_doctor or request.user.is_administrator):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=status.HTTP_403_FORBIDDEN)

        patient = self.get_object()
        password = request.data.get('password')
        if not password or len(password) < 6:
            return Response({'detail': 'Parol kamida 6 ta belgidan iborat bo‘lishi kerak.'}, status=status.HTTP_400_BAD_REQUEST)

        if not patient.user:
            return Response({'detail': 'Bemor foydalanuvchisi topilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        patient.user.set_password(password)
        patient.user.save(update_fields=['password'])
        return Response({'detail': 'Parol muvaffaqiyatli o‘rnatildi.'}, status=status.HTTP_200_OK)
