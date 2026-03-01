from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shared.auth"
    label = "shared_auth"
    verbose_name = "サービス間認証 (Service JWT)"
