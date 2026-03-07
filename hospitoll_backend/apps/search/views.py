"""
Search and Cache API Views
REST API endpoints for full-text search and cache management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.core.paginator import Paginator
import logging

from core.search_service import FullTextSearchService
from core.cache_service import CacheService, CacheInvalidationService, QueryOptimizationHelper

logger = logging.getLogger(__name__)


class SearchViewSet(viewsets.ViewSet):
    """
    Search API endpoints for doctors, clinics, patients, appointments, medical records
    
    Endpoints:
    - GET /search/ - Full-text search
    - GET /search/suggestions/ - Search suggestions
    - GET /search/doctors/ - Search doctors
    - GET /search/doctors/{id}/availability/ - Doctor availability
    - GET /search/specialties/ - Search by specialty
    """
    
    permission_classes = [IsAuthenticated]
    search_service = FullTextSearchService()
    
    @action(detail=False, methods=['get'])
    def list_all(self, request):
        """
        Full-text search across all models
        
        Query params:
        - q: Search query (required, min 3 chars)
        - models: Comma-separated model names (optional)
        - limit: Max results per model (default: 20)
        
        GET /search/?q=john&models=doctors,clinics&limit=10
        """
        try:
            query = request.query_params.get('q')
            if not query or len(query) < 3:
                return Response(
                    {'error': 'Search query must be at least 3 characters'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            models = request.query_params.get('models', '')
            models = [m.strip() for m in models.split(',')] if models else None
            
            limit = int(request.query_params.get('limit', 20))
            
            # Check cache first
            cache_key = f"search:{query}:{models}:{limit}"
            cached_result = CacheService.get(cache_key)
            if cached_result:
                return Response(cached_result)
            
            # Perform search
            result = self.search_service.search(query, models, limit)
            
            # Cache result
            CacheService.set(cache_key, result, 900)  # 15 minutes
            
            return Response(result)
        
        except ValueError as e:
            return Response(
                {'error': 'Invalid limit parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='suggestions')
    def suggestions(self, request):
        """
        Get search suggestions
        
        Query params:
        - q: Partial query (required, min 2 chars)
        - model: Optional model filter (doctors, clinics, specialties)
        
        GET /search/suggestions/?q=jo&model=doctors
        """
        try:
            query = request.query_params.get('q')
            if not query or len(query) < 2:
                return Response(
                    {'suggestions': []},
                    status=status.HTTP_200_OK
                )
            
            model = request.query_params.get('model')
            
            suggestions = self.search_service.get_search_suggestions(query, model)
            
            return Response({
                'query': query,
                'suggestions': suggestions
            })
        
        except Exception as e:
            logger.error(f"Suggestions error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='doctors')
    def search_doctors(self, request):
        """
        Search doctors with optional filters
        
        Query params:
        - q: Search query
        - clinic_id: Filter by clinic
        - specialty_id: Filter by specialty
        - limit: Max results (default: 20)
        
        GET /search/doctors/?q=john&clinic_id=1
        """
        try:
            query = request.query_params.get('q')
            clinic_id = request.query_params.get('clinic_id')
            specialty_id = request.query_params.get('specialty_id')
            limit = int(request.query_params.get('limit', 20))
            
            # Get doctors with cache
            doctors = QueryOptimizationHelper.get_doctors_with_cache(
                clinic_id=int(clinic_id) if clinic_id else None,
                specialty_id=int(specialty_id) if specialty_id else None
            )
            
            # Filter by query if provided
            if query:
                query_lower = query.lower()
                doctors = [
                    d for d in doctors
                    if query_lower in f"{d['first_name']} {d['last_name']}".lower() or
                       query_lower in d.get('specialty__name', '').lower()
                ]
            
            # Apply limit
            doctors = doctors[:limit]
            
            return Response({
                'count': len(doctors),
                'results': doctors
            })
        
        except (ValueError, TypeError) as e:
            return Response(
                {'error': 'Invalid parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Doctor search error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='doctors/(?P<doctor_id>[0-9]+)/availability')
    def doctor_availability(self, request, doctor_id=None):
        """
        Get doctor availability
        
        Query params:
        - date: Specific date (optional, YYYY-MM-DD)
        
        GET /search/doctors/1/availability/?date=2024-02-20
        """
        try:
            date = request.query_params.get('date')
            
            # Here you would fetch actual availability
            # For now, return cached or dummy data
            cache_key = f"availability:{doctor_id}:{date}"
            cached = CacheService.get(cache_key)
            if cached:
                return Response(cached)
            
            # TODO: Implement actual availability fetching from Appointment model
            availability = {
                'doctor_id': doctor_id,
                'date': date,
                'slots': [],
                'available_count': 0
            }
            
            CacheService.set(cache_key, availability, 600)  # 10 minutes
            
            return Response(availability)
        
        except Exception as e:
            logger.error(f"Availability error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='specialties')
    def specialties(self, request):
        """
        Get all specialties
        
        GET /search/specialties/
        """
        try:
            from apps.doctors.models import Specialization
            
            cache_key = "specialties:list"
            cached = CacheService.get(cache_key)
            if cached:
                return Response({'specialties': cached})
            
            specialties = list(Specialization.objects.values('id', 'name'))
            
            CacheService.set(cache_key, specialties, 3600)  # 1 hour
            
            return Response({'specialties': specialties})
        
        except Exception as e:
            logger.error(f"Specialties error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CacheManagementViewSet(viewsets.ViewSet):
    """
    Cache management endpoints (admin only)
    
    Endpoints:
    - POST /cache/invalidate/ - Invalidate cache
    - POST /cache/clear/ - Clear all cache
    - GET /cache/stats/ - Cache statistics
    """
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=False, methods=['post'])
    def invalidate(self, request):
        """
        Invalidate specific cache patterns
        
        Request body:
        {
            "patterns": ["doctors:*", "clinics:detail:1"]
        }
        
        POST /cache/invalidate/
        """
        try:
            patterns = request.data.get('patterns', [])
            
            if not patterns:
                return Response(
                    {'error': 'patterns field is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            deleted_count = 0
            for pattern in patterns:
                if '*' in pattern:
                    deleted_count += CacheService.delete_pattern(pattern)
                else:
                    if CacheService.delete(pattern):
                        deleted_count += 1
            
            return Response({
                'message': f'Cache invalidated: {deleted_count} keys deleted',
                'patterns': patterns,
                'deleted': deleted_count
            })
        
        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """
        Clear all cache
        
        POST /cache/clear/
        """
        try:
            CacheService.clear_all()
            
            return Response({
                'message': 'All cache cleared successfully'
            })
        
        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get cache statistics
        
        GET /cache/stats/
        """
        try:
            from django.core.cache import cache
            
            # Get cache backend info
            cache_backend = cache.__class__.__name__
            
            stats = {
                'backend': cache_backend,
                'configured': True,
                'location': getattr(cache, '_options', {}).get('LOCATION', 'N/A'),
                'message': 'Cache is operational'
            }
            
            return Response(stats)
        
        except Exception as e:
            logger.error(f"Cache stats error: {str(e)}")
            return Response({
                'backend': 'unknown',
                'configured': False,
                'error': str(e)
            })
    
    @action(detail=False, methods=['post'], url_path='invalidate-doctors')
    def invalidate_doctors(self, request):
        """Invalidate doctor cache"""
        doctor_id = request.data.get('doctor_id')
        CacheInvalidationService.invalidate_doctor_cache(doctor_id)
        return Response({'message': 'Doctor cache invalidated'})
    
    @action(detail=False, methods=['post'], url_path='invalidate-clinics')
    def invalidate_clinics(self, request):
        """Invalidate clinic cache"""
        clinic_id = request.data.get('clinic_id')
        CacheInvalidationService.invalidate_clinic_cache(clinic_id)
        return Response({'message': 'Clinic cache invalidated'})
    
    @action(detail=False, methods=['post'], url_path='invalidate-appointments')
    def invalidate_appointments(self, request):
        """Invalidate appointment cache"""
        appointment_id = request.data.get('appointment_id')
        CacheInvalidationService.invalidate_appointment_cache(appointment_id)
        return Response({'message': 'Appointment cache invalidated'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_api(request):
    """
    Quick search endpoint (POST friendly)
    
    GET /api/v1/search/?q=query&models=doctors,clinics&limit=20
    """
    search_service = FullTextSearchService()
    
    query = request.query_params.get('q')
    if not query:
        return Response(
            {'error': 'q parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    models = request.query_params.get('models', '')
    models = [m.strip() for m in models.split(',')] if models else None
    
    try:
        result = search_service.search(query, models, 20)
        return Response(result)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
