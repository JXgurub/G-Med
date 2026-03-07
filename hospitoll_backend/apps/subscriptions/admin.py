# Admin configuration for subscriptions app
from django.contrib import admin
from .models import SubscriptionPlan, Subscription, SubscriptionPayment


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('sort_order',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('get_subscriber_name', 'plan', 'status', 'end_date', 'created_at')
    list_filter = ('status', 'subscriber_type', 'created_at')
    search_fields = ('clinic__name', 'pharmacy__name')
    ordering = ('-created_at',)
    
    def get_subscriber_name(self, obj):
        return obj.clinic.name if obj.clinic else obj.pharmacy.name
    get_subscriber_name.short_description = 'Subscriber'


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('subscription__clinic__name', 'subscription__pharmacy__name', 'transaction_id')
    ordering = ('-created_at',)
