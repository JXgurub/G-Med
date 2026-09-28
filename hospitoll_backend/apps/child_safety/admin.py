from django.contrib import admin

from .models import SafetyRegion, SafetyVote, SafetyVoteAudit


@admin.register(SafetyRegion)
class SafetyRegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'parent', 'is_active', 'created_at')
    list_filter = ('level', 'is_active')
    search_fields = ('name',)


@admin.register(SafetyVote)
class SafetyVoteAdmin(admin.ModelAdmin):
    list_display = ('region', 'choice', 'is_active', 'created_at', 'revoked_at')
    list_filter = ('choice', 'is_active')
    readonly_fields = tuple(field.name for field in SafetyVote._meta.fields)
    search_fields = ('region__name',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SafetyVoteAudit)
class SafetyVoteAuditAdmin(admin.ModelAdmin):
    list_display = ('region', 'action', 'choice', 'actor', 'created_at')
    list_filter = ('action', 'choice')
    readonly_fields = tuple(field.name for field in SafetyVoteAudit._meta.fields)
    search_fields = ('region__name', 'reason')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
