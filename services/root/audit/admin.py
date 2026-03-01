from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_hash", "prev_hash", "created_at")
    list_filter = ("created_at",)
    search_fields = ("event_hash", "prev_hash")
    readonly_fields = ("prev_hash", "event_hash", "payload", "signature", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
