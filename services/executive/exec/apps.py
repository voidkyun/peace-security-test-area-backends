from django.apps import AppConfig


class ExecAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "exec"
    label = "exec"
    verbose_name = "秩序実行（Evaluation / EXEC_ACTION）"
