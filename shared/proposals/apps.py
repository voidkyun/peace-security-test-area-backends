from django.apps import AppConfig


class ProposalsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shared.proposals"
    label = "shared_proposals"
    verbose_name = "Proposal（意思決定最小単位）"
