from django.apps import AppConfig


class LawsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "laws"
    label = "laws"
    verbose_name = "法・法体系（Law / Lawset）"
