from django.contrib import admin
from .models import Evaluation, ExecutionQueueItem


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(ExecutionQueueItem)
class ExecutionQueueItemAdmin(admin.ModelAdmin):
    list_display = ("id", "proposal_id", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")
