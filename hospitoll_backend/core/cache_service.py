"""
Caching Service
Implements Redis-based caching for frequently accessed data
"""

import json
import logging
from functools import wraps
from typing import Any, Callable, Optional, Union
from uuid import UUID
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis caching service with cache invalidation support
    """
    
    # Cache key prefixes and timeouts
    CACHE_TIMEOUTS = {
        'doctors_list': 3600,           # 1 hour
        'doctors_detail': 1800,         # 30 minutes
        'clinics_list': 3600,           # 1 hour
        'clinics_detail': 1800,         # 30 minutes
        'appointments': 300,             # 5 minutes
        'availability': 600,             # 10 minutes
        'patient_records': 1800,        # 30 minutes
        'pharmaceuticals': 3600,        # 1 hour
        'subscriptions': 1800,          # 30 minutes
        'payments': 600,                # 10 minutes
        'statistics': 3600,             # 1 hour
        'search_results': 900,          # 15 minutes
    }
    
    CACHE_KEYS = {
        'doctors_list': 'doctors:list',
        'doctors_detail': 'doctors:detail:{}',
        'doctor_appointments': 'doctors:appointments:{}',
        'clinics_list': 'clinics:list',
        'clinics_detail': 'clinics:detail:{}',
        'appointments_list': 'appointments:list:{}',
        'appointments_detail': 'appointments:detail:{}',
        'availability': 'availability:{}:{}',
        'patient_records': 'patients:records:{}',
        'patient_detail': 'patients:detail:{}',
        'pharmaceuticals': 'pharmaceuticals:list',
        'subscriptions': 'subscriptions:{}',
        'payments': 'payments:{}',
        'statistics': 'statistics:{}',
        'search_results': 'search:{}',
    }
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get value from cache
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            logger.error(f"Cache get error for {key}: {str(e)}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful
        """
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache set: {key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {str(e)}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        try:
            cache.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {str(e)}")
            return False
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all cache entries matching pattern
        
        Args:
            pattern: Pattern to match (e.g., 'doctors:*')
            
        Returns:
            Number of keys deleted
        """
        try:
            from django.core.cache.backends.redis import RedisCache
            
            if isinstance(cache, RedisCache):
                client = cache._cache
                keys = client.keys(pattern)  # type: ignore[attr-defined]
                if keys:
                    deleted = client.delete(*keys)
                    logger.debug(f"Cache pattern deleted: {pattern} ({deleted} keys)")
                    return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache pattern delete error for {pattern}: {str(e)}")
            return 0
    
    @staticmethod
    def clear_all() -> bool:
        """Clear all cache"""
        try:
            cache.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")
            return False
    
    @staticmethod
    def get_many(keys: list) -> dict:
        """Get multiple cache values"""
        try:
            return cache.get_many(keys)
        except Exception as e:
            logger.error(f"Cache get_many error: {str(e)}")
            return {}
    
    @staticmethod
    def set_many(data: dict, timeout: int = 300) -> bool:
        """Set multiple cache values"""
        try:
            cache.set_many(data, timeout)
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {str(e)}")
            return False


def cache_result(timeout: int = 300, key_prefix: str = ''):
    """
    Decorator to cache function results
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Cache key prefix
        
    Usage:
        @cache_result(timeout=3600, key_prefix='doctors')
        def get_doctors():
            return Doctor.objects.all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = CacheService.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Call function and cache result
            result = func(*args, **kwargs)
            CacheService.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(patterns: list):
    """
    Decorator to invalidate cache after function execution
    
    Args:
        patterns: List of cache key patterns to invalidate
        
    Usage:
        @invalidate_cache(['doctors:*', 'clinics:detail:1'])
        def update_doctor(doctor_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            # Invalidate cache patterns
            for pattern in patterns:
                if '*' in pattern:
                    CacheService.delete_pattern(pattern)
                else:
                    CacheService.delete(pattern)
            
            return result
        
        return wrapper
    return decorator


class CacheInvalidationService:
    """
    Service to manage cache invalidation across models
    """
    
    @staticmethod
    def invalidate_doctor_cache(doctor_id: Union[int, str, UUID, None] = None):
        """Invalidate doctor-related cache"""
        patterns = [
            'doctors:list',
            f'doctors:detail:{doctor_id}' if doctor_id else 'doctors:detail:*',
            f'doctors:appointments:{doctor_id}' if doctor_id else 'doctors:appointments:*',
            'availability:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_clinic_cache(clinic_id: Union[int, str, UUID, None] = None):
        """Invalidate clinic-related cache"""
        patterns = [
            'clinics:list',
            f'clinics:detail:{clinic_id}' if clinic_id else 'clinics:detail:*',
            'doctors:list',
            'doctors:detail:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_appointment_cache(appointment_id: Union[int, str, UUID, None] = None):
        """Invalidate appointment-related cache"""
        patterns = [
            'appointments:list:*',
            f'appointments:detail:{appointment_id}' if appointment_id else 'appointments:detail:*',
            'availability:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_patient_cache(patient_id: Union[int, str, UUID, None] = None):
        """Invalidate patient-related cache"""
        patterns = [
            f'patients:detail:{patient_id}' if patient_id else 'patients:detail:*',
            f'patients:records:{patient_id}' if patient_id else 'patients:records:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_payment_cache(clinic_id: Union[int, str, UUID, None] = None):
        """Invalidate payment-related cache"""
        patterns = [
            f'payments:{clinic_id}' if clinic_id else 'payments:*',
            'statistics:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_subscription_cache(clinic_id: Union[int, str, UUID, None] = None):
        """Invalidate subscription-related cache"""
        patterns = [
            f'subscriptions:{clinic_id}' if clinic_id else 'subscriptions:*',
        ]
        for pattern in patterns:
            if '*' in pattern:
                CacheService.delete_pattern(pattern)
            else:
                CacheService.delete(pattern)
    
    @staticmethod
    def invalidate_all():
        """Clear all cache"""
        CacheService.clear_all()


class QueryOptimizationHelper:
    """
    Helper class for optimizing database queries with caching
    """
    
    @staticmethod
    def get_doctors_with_cache(clinic_id: Optional[int] = None, specialty_id: Optional[int] = None) -> list:
        """Get doctors with caching and select_related optimization"""
        from apps.doctors.models import Doctor
        
        cache_key = f"doctors:list:{clinic_id}:{specialty_id}"
        cached = CacheService.get(cache_key)
        
        if cached is not None:
            return cached
        
        query = Doctor.objects.select_related(
            'clinic',
            'specialty'
        ).prefetch_related(
            'qualifications'
        )
        
        if clinic_id:
            query = query.filter(clinic_id=clinic_id)
        if specialty_id:
            query = query.filter(specialty_id=specialty_id)
        
        result = list(query.values(
            'id', 'first_name', 'last_name', 'specialty__name',
            'clinic__name', 'phone', 'is_active'
        ))
        
        CacheService.set(
            cache_key,
            result,
            CacheService.CACHE_TIMEOUTS['doctors_list']
        )
        
        return result
    
    @staticmethod
    def get_appointments_with_cache(clinic_id: int, date: Optional[str] = None) -> list:
        """Get appointments with caching and prefetch optimization"""
        from apps.medical.models import Appointment
        
        cache_key = f"appointments:list:{clinic_id}:{date}"
        cached = CacheService.get(cache_key)
        
        if cached is not None:
            return cached
        
        query = Appointment.objects.select_related(
            'doctor',
            'patient',
            'clinic'
        ).filter(
            clinic_id=clinic_id
        )
        
        if date:
            query = query.filter(appointment_datetime__date=date)
        
        result = list(query.values(
            'id', 'doctor__first_name', 'doctor__last_name',
            'patient__first_name', 'patient__last_name',
            'appointment_datetime', 'status'
        ))
        
        CacheService.set(
            cache_key,
            result,
            CacheService.CACHE_TIMEOUTS['appointments']
        )
        
        return result
    
    @staticmethod
    def get_patient_records_with_cache(patient_id: int) -> list:
        """Get patient medical records with caching"""
        from apps.medical.models import MedicalRecord
        
        cache_key = f"patients:records:{patient_id}"
        cached = CacheService.get(cache_key)
        
        if cached is not None:
            return cached
        
        result = list(MedicalRecord.objects.select_related(
            'patient',
            'doctor'
        ).filter(
            patient_id=patient_id
        ).values(
            'id', 'diagnosis', 'symptoms', 'treatment_plan',
            'doctor__first_name', 'doctor__last_name',
            'created_at'
        ).order_by('-created_at'))
        
        CacheService.set(
            cache_key,
            result,
            CacheService.CACHE_TIMEOUTS['patient_records']
        )
        
        return result
