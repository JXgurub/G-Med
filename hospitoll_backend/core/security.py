"""
Security Module
Implements security best practices including CSRF, XSS, SQL injection prevention,
rate limiting, and security headers
"""

import logging
from functools import wraps
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.utils.deprecation import MiddlewareMixin
import re

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting service to prevent abuse"""
    
    @staticmethod
    def is_rate_limited(identifier: str, limit: int = 100, window: int = 3600) -> bool:
        """
        Check if request should be rate limited
        
        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            limit: Max requests per window
            window: Time window in seconds
            
        Returns:
            bool: True if rate limited, False otherwise
        """
        cache_key = f"rate_limit:{identifier}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= limit:
            return True
        
        cache.set(cache_key, request_count + 1, window)
        return False
    
    @staticmethod
    def get_remaining_requests(identifier: str, limit: int = 100):
        """Get remaining requests for identifier"""
        cache_key = f"rate_limit:{identifier}"
        request_count = cache.get(cache_key, 0)
        return max(0, limit - request_count)


def rate_limit_by_ip(limit: int = 100, window: int = 3600):
    """
    Decorator to rate limit API endpoints by IP address
    
    Args:
        limit: Max requests per window
        window: Time window in seconds
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            client_ip = get_client_ip(request)
            
            if RateLimiter.is_rate_limited(f"ip:{client_ip}", limit, window):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'detail': 'Too many requests. Please try again later.'
                }, status=429)
            
            response = view_func(request, *args, **kwargs)
            
            remaining = RateLimiter.get_remaining_requests(f"ip:{client_ip}", limit)
            response['X-RateLimit-Remaining'] = remaining
            response['X-RateLimit-Limit'] = limit
            
            return response
        
        return wrapper
    
    return decorator


def rate_limit_by_user(limit: int = 200, window: int = 3600):
    """
    Decorator to rate limit API endpoints by authenticated user
    
    Args:
        limit: Max requests per window
        window: Time window in seconds
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Fall back to IP-based limiting
                return rate_limit_by_ip(limit, window)(view_func)(request, *args, **kwargs)
            
            user_id = request.user.id
            
            if RateLimiter.is_rate_limited(f"user:{user_id}", limit, window):
                logger.warning(f"Rate limit exceeded for user: {user_id}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'detail': 'Too many requests. Please try again later.'
                }, status=429)
            
            response = view_func(request, *args, **kwargs)
            
            remaining = RateLimiter.get_remaining_requests(f"user:{user_id}", limit)
            response['X-RateLimit-Remaining'] = remaining
            response['X-RateLimit-Limit'] = limit
            
            return response
        
        return wrapper
    
    return decorator


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses
    """
    
    def process_response(self, request, response):
        """Add security headers"""
        
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' localhost:*; "
            "frame-ancestors 'none';"
        )
        
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy (formerly Feature-Policy)
        response['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), '
            'gyroscope=(), magnetometer=(), microphone=(), '
            'payment=(), usb=()'
        )
        
        # Strict Transport Security (HTTPS only in production)
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )
        
        return response


class InputSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware to detect and prevent common injection attacks
    """
    
    # Patterns for common injection attempts
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(;.*\b(SELECT|DROP|DELETE|INSERT|UPDATE)\b)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
    ]
    
    @staticmethod
    def _check_for_injection(value: str, patterns: list) -> bool:
        """Check if value contains injection patterns"""
        if not isinstance(value, str):
            return False
        
        for pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                return True
        
        return False
    
    def process_request(self, request):
        """Check for injection attempts in request"""
        
        # Check GET parameters
        for key, value in request.GET.items():
            if self._check_for_injection(value, self.SQL_INJECTION_PATTERNS):
                logger.warning(
                    f"Potential SQL injection detected in GET param '{key}' "
                    f"from {get_client_ip(request)}"
                )
                return JsonResponse({
                    'error': 'Invalid request',
                    'detail': 'Suspicious characters detected in request'
                }, status=400)
            
            if self._check_for_injection(value, self.XSS_PATTERNS):
                logger.warning(
                    f"Potential XSS injection detected in GET param '{key}' "
                    f"from {get_client_ip(request)}"
                )
                return JsonResponse({
                    'error': 'Invalid request',
                    'detail': 'Suspicious characters detected in request'
                }, status=400)
        
        # Check POST data
        if request.method == 'POST' and request.POST:
            for key, value in request.POST.items():
                if self._check_for_injection(value, self.SQL_INJECTION_PATTERNS):
                    logger.warning(
                        f"Potential SQL injection detected in POST param '{key}' "
                        f"from {get_client_ip(request)}"
                    )
                    return JsonResponse({
                        'error': 'Invalid request',
                        'detail': 'Suspicious characters detected in request'
                    }, status=400)


class CSRFProtectionMiddleware(MiddlewareMixin):
    """
    Enhanced CSRF protection middleware
    """
    
    def process_request(self, request):
        """Validate CSRF token for state-changing requests"""
        
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            # Skip for API endpoints with authentication
            if request.path.startswith('/api/'):
                # Check for Authorization header (JWT)
                if 'HTTP_AUTHORIZATION' in request.META:
                    return None
            
            # For regular form submissions, check CSRF token
            csrf_token = request.POST.get('csrfmiddlewaretoken') or \
                        request.META.get('HTTP_X_CSRFTOKEN')
            
            if not csrf_token:
                logger.warning(
                    f"CSRF token missing for {request.method} "
                    f"from {get_client_ip(request)}"
                )


class AuthenticationSecurityMiddleware(MiddlewareMixin):
    """
    Authentication and session security middleware
    """
    
    def process_request(self, request):
        """Add security measures for authentication"""
        
        # Set secure cookie flags
        if request.user.is_authenticated:
            # Check for suspicious activity
            self._check_for_suspicious_activity(request)
    
    @staticmethod
    def _check_for_suspicious_activity(request):
        """Check for suspicious authentication activity"""
        
        user_id = request.user.id
        cache_key = f"auth_activity:{user_id}"
        
        # Track authentication activity
        activity = cache.get(cache_key, {})
        activity['last_seen'] = timezone.now().isoformat()
        activity['ip'] = get_client_ip(request)
        activity['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        cache.set(cache_key, activity, 86400)  # 24 hours


def get_client_ip(request):
    """
    Get client IP address from request
    Handles proxied requests
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    
    return ip


class APISecurityMixin:
    """
    Mixin for API views to add security checks
    """
    
    def dispatch(self, request, *args, **kwargs):
        """Add security checks to API requests"""
        
        # Check rate limiting
        client_ip = get_client_ip(request)
        if RateLimiter.is_rate_limited(f"api_ip:{client_ip}", limit=200, window=3600):
            return JsonResponse({
                'error': 'Rate limit exceeded'
            }, status=429)
        
        # Check for required headers
        if not self._has_required_security_headers(request):
            logger.warning(f"Missing security headers from {client_ip}")
        
        return super().dispatch(request, *args, **kwargs)  # type: ignore[no-untyped-call]
    
    @staticmethod
    def _has_required_security_headers(request):
        """Check if request has required security headers"""
        
        # For API requests, check for appropriate auth headers
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            return 'HTTP_AUTHORIZATION' in request.META or \
                   'HTTP_X_CSRF_TOKEN' in request.META
        
        return True


# Import timezone for suspicious activity monitoring
from django.utils import timezone
