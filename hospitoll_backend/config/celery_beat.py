# Celery Beat Schedule Configuration
# Add this to your settings.py for automatic task scheduling

CELERY_BEAT_SCHEDULE = {
    # Check and deactivate expired subscriptions - twice daily
    'check-expired-subscriptions': {
        'task': 'apps.subscriptions.tasks.check_and_deactivate_expired_subscriptions',
        'schedule': 43200.0,  # Every 12 hours
    },
    
    # Send subscription expiry reminders - daily at 9 AM
    'send-subscription-reminders': {
        'task': 'apps.subscriptions.tasks.send_subscription_expiry_reminders',
        'schedule': 86400.0,  # Every 24 hours
    },
    
    # Convert trial subscriptions to pending payment - daily
    'trial-to-pending': {
        'task': 'apps.subscriptions.tasks.trial_to_pending_payment',
        'schedule': 86400.0,  # Every 24 hours
    },
    
    # Send appointment reminders - 3 times daily
    'send-appointment-reminders': {
        'task': 'apps.medical.tasks.send_appointment_reminders',
        'schedule': 28800.0,  # Every 8 hours
    },
    
    # Check overdue invoices - daily
    'check-overdue-invoices': {
        'task': 'apps.payments.tasks.check_overdue_invoices',
        'schedule': 86400.0,  # Every 24 hours
    },
    
    # Send payment reminders - daily
    'send-payment-reminders': {
        'task': 'apps.payments.tasks.send_payment_reminders',
        'schedule': 86400.0,  # Every 24 hours
    },
}

# To use these, add to your settings.py:
# from celery.schedules import crontab
# CELERY_BEAT_SCHEDULE = {
#     'send-appointment-reminders': {
#         'task': 'apps.medical.tasks.send_appointment_reminders',
#         'schedule': crontab(hour=9, minute=0),  # Every day at 9 AM
#     },
# }
