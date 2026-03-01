from django.contrib import admin
from .models import Law, Lawset, LawsetMembership


@admin.register(Law)
class LawAdmin(admin.ModelAdmin):
    list_display = ("law_id", "law_version", "title", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("law_id", "title")


@admin.register(Lawset)
class LawsetAdmin(admin.ModelAdmin):
    list_display = ("lawset_id", "version", "effective_at", "created_at")
    list_filter = ("lawset_id",)


@admin.register(LawsetMembership)
class LawsetMembershipAdmin(admin.ModelAdmin):
    list_display = ("lawset", "law", "order")
    list_filter = ("lawset",)
