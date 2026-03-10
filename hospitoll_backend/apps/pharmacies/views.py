from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Pharmacy, Medicine, PharmacyMarchandise
from .serializers import (
    PharmacySerializer,
    PharmacyCreateSerializer,
    PharmacyUpdateSerializer,
    MedicineSerializer,
    PharmacyMarchandiseSerializer,
)


class PharmacyViewSet(viewsets.ModelViewSet):
    queryset = Pharmacy.objects.select_related('owner').all()
    serializer_class = PharmacySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action == 'my':
            return [permissions.IsAuthenticated()]
        # For create, update, delete - require authentication
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return PharmacyCreateSerializer
        if self.action in ['update', 'partial_update']:
            return PharmacyUpdateSerializer
        return PharmacySerializer

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=404)
        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=404)
        serializer = self.get_serializer(pharmacy)
        return Response(serializer.data)


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [permissions.IsAuthenticated]


class PharmacyMarchandiseViewSet(viewsets.ModelViewSet):
    queryset = PharmacyMarchandise.objects.select_related('pharmacy', 'medicine').all()
    serializer_class = PharmacyMarchandiseSerializer
    filterset_fields = ['pharmacy', 'medicine', 'is_available']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['delete'], permission_classes=[permissions.IsAuthenticated], url_path='clear-all')
    def clear_all(self, request):
        if not request.user.is_pharmacy:
            return Response({'detail': 'Faqat dorixona egasi ruxsatiga ega.'}, status=status.HTTP_403_FORBIDDEN)

        pharmacy = Pharmacy.objects.filter(owner=request.user).first()
        if not pharmacy:
            return Response({'detail': 'Dorixona topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        qs = PharmacyMarchandise.objects.filter(pharmacy=pharmacy)
        deleted_count = qs.count()
        qs.delete()

        return Response({'deleted_count': deleted_count}, status=status.HTTP_200_OK)
