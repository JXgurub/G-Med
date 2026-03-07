"""
Celery configuration for Hospitoll platform.
Handles asynchronous tasks like:
- Subscription expiry checks
- Notification sending
- Report generation
"""

import os
from celery import Celery
from celery.signals import task_failure

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('hospitoll')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@task_failure.connect
def celery_task_failure_handler(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **other,
):
    """Forward Celery task failures to centralized error monitoring."""
    try:
        from core.error_logging import ErrorLogger

        ErrorLogger.log_error(
            error_type='celery_task_failure',
            message=str(exception) if exception else 'Celery task failed',
            context={
                'task_name': getattr(sender, 'name', str(sender)) if sender else None,
                'task_id': task_id,
                'args': args,
                'kwargs': kwargs,
                'einfo': str(einfo) if einfo else None,
            },
            severity='error',
        )
    except Exception:
        # Avoid secondary failures inside signal handler.
        pass
