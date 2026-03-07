"""
Error Logging and Monitoring Module
Handles centralized error tracking, logging, and monitoring
"""

import logging
import json
from typing import Optional
from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.apps import apps
from functools import wraps
import sys
import traceback

logger = logging.getLogger(__name__)


class ErrorLogger:
    """Centralized error logging service"""

    @staticmethod
    def _safe_json_dumps(data, **kwargs):
        return json.dumps(data, default=str, **kwargs)

    @staticmethod
    def _safe_json_loads(value: str):
        try:
            return json.loads(value)
        except Exception:
            return {'raw': value}

    @staticmethod
    def _persist_system_alert(
        error_type: str,
        message: str,
        severity: str,
        context: Optional[dict] = None,
        traceback_text: str = '',
    ):
        try:
            SystemAlert = apps.get_model('site_settings', 'SystemAlert')
            safe_context = ErrorLogger._safe_json_loads(ErrorLogger._safe_json_dumps(context or {}))
            normalized_severity = severity if severity in {'warning', 'error', 'critical'} else 'error'
            SystemAlert.objects.create(
                alert_type=str(error_type or 'unknown_error'),
                message=str(message or ''),
                severity=normalized_severity,
                context=safe_context,
                traceback=str(traceback_text or ''),
            )
        except Exception as persist_error:
            logger.error(f"Failed to persist SystemAlert: {persist_error}")
    
    @staticmethod
    def log_error(error_type: str, message: str, context: Optional[dict] = None, severity: str = 'error'):
        """
        Log an error with context information
        
        Args:
            error_type: Type of error (e.g., 'api_error', 'database_error')
            message: Error message
            context: Additional context data
            severity: Severity level ('error', 'critical', 'warning')
        """
        error_data = {
            'error_type': error_type,
            'message': message,
            'context': context or {},
            'severity': severity
        }

        ErrorLogger._persist_system_alert(
            error_type=error_type,
            message=message,
            severity=severity,
            context=context,
        )
        
        if severity == 'critical':
            logger.critical(ErrorLogger._safe_json_dumps(error_data))
            ErrorLogger.send_alert_notification(error_data)
        elif severity == 'error':
            logger.error(ErrorLogger._safe_json_dumps(error_data))
        else:
            logger.warning(ErrorLogger._safe_json_dumps(error_data))
    
    @staticmethod
    def log_exception(exception: Exception, context: Optional[dict] = None):
        """
        Log an exception with full traceback
        
        Args:
            exception: The exception object
            context: Additional context data
        """
        error_data = {
            'error_type': type(exception).__name__,
            'message': str(exception),
            'traceback': traceback.format_exc(),
            'context': context or {},
            'severity': 'error'
        }
        
        logger.error(ErrorLogger._safe_json_dumps(error_data), exc_info=True)
        ErrorLogger._persist_system_alert(
            error_type=type(exception).__name__,
            message=str(exception),
            severity='error',
            context=context,
            traceback_text=error_data['traceback'],
        )
    
    @staticmethod
    def send_alert_notification(error_data: dict):
        """
        Send alert notification for critical errors
        
        Args:
            error_data: Error details to include in notification
        """
        try:
            subject = f"🚨 CRITICAL ERROR: {error_data.get('error_type')}"
            message = f"""
CRITICAL ERROR ALERT

Type: {error_data.get('error_type')}
Message: {error_data.get('message')}

Context:
{ErrorLogger._safe_json_dumps(error_data.get('context'), indent=2)}

Time: {error_data.get('timestamp', 'N/A')}

Please investigate immediately!

---
Hospitoll Monitoring System
            """
            
            # Send to admin emails
            admin_emails = [
                email for name, email in settings.ADMINS
            ]
            
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True
                )
        except Exception as e:
            logger.error(f"Failed to send alert notification: {str(e)}")
    
    @staticmethod
    def get_error_summary():
        """Get summary of recent errors"""
        # This would typically query a monitoring database
        # For now, it returns placeholder
        return {
            'total_errors_24h': 0,
            'critical_errors': 0,
            'last_error': None
        }


def api_error_handler(view_func):
    """
    Decorator to catch and log API errors
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except Exception as e:
            # Extract request context if available
            request = args[1] if len(args) > 1 else None
            
            context = {
                'view': view_func.__name__,
                'method': request.method if request else 'N/A',
                'path': request.path if request else 'N/A',
                'user_id': request.user.id if request and request.user.is_authenticated else None,
            }
            
            ErrorLogger.log_exception(e, context)
            
            return JsonResponse({
                'error': 'An error occurred',
                'error_type': type(e).__name__,
                'message': str(e) if settings.DEBUG else 'Internal server error'
            }, status=500)
    
    return wrapper


class ErrorLoggingMiddleware:
    """
    Middleware to log all errors and exceptions
    """

    EXCLUDED_ERROR_PATHS = {
        '/api/v1/site-settings/system-alerts/client/',
    }
    EXPECTED_AUTH_NOISE_PATHS = {
        '/api/v1/clinics/my/',
        '/api/v1/pharmacies/my/',
    }
    EXPECTED_AUTH_NOISE_PREFIXES = (
        '/api/v1/site-settings/system-alerts/admin/',
        '/api/v1/site-settings/contact-leads/admin/',
        '/api/v1/clinics/staff-messages/',
        '/api/v1/users/profile/',
        '/api/v1/users/patient-token/',
        '/api/v1/patients/my/',
        '/api/v1/doctors/my/',
        '/api/v1/medical/appointments/doctor_dashboard_stats/',
    )
    STATIC_PATH_PREFIXES = ('/static/', '/media/')
    STATIC_FILE_PATHS = {'/favicon.ico', '/'}
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            
            # Log 4xx and 5xx responses
            if response.status_code >= 400:
                self._log_response_error(request, response)
            
            return response
        except Exception as e:
            context = {
                'method': request.method,
                'path': request.path,
                'user_id': request.user.id if request.user.is_authenticated else None,
            }
            ErrorLogger.log_exception(e, context)
            
            # Return error response
            return JsonResponse({
                'error': 'An error occurred',
                'message': str(e) if settings.DEBUG else 'Internal server error'
            }, status=500)
    
    def _log_response_error(self, request, response):
        """Log HTTP error responses"""
        path = request.path or ''

        if response.status_code in {400, 401, 403, 404}:
            return

        if path in self.EXCLUDED_ERROR_PATHS:
            return

        if path in self.STATIC_FILE_PATHS or path.startswith(self.STATIC_PATH_PREFIXES):
            return

        if path in self.EXPECTED_AUTH_NOISE_PATHS and response.status_code in {401, 403, 404}:
            return

        if response.status_code in {401, 403} and path.startswith(self.EXPECTED_AUTH_NOISE_PREFIXES):
            return

        error_data = {
            'status_code': response.status_code,
            'method': request.method,
            'path': path,
            'user_id': request.user.id if request.user.is_authenticated else None,
            'remote_ip': self._get_client_ip(request),
        }
        
        if response.status_code >= 500:
            ErrorLogger.log_error(
                'http_error',
                f"HTTP {response.status_code}",
                error_data,
                'error'
            )
        elif response.status_code >= 400:
            ErrorLogger.log_error(
                'http_error',
                f"HTTP {response.status_code}",
                error_data,
                'warning'
            )
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record, record, message_dict):
        super(StructuredFormatter, self).add_fields(log_record, record, message_dict)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
