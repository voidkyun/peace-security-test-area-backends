"""
Service JWT を発行して標準出力に出力する。他サービス呼び出しやテスト用。
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from shared.auth import issue_jwt


class Command(BaseCommand):
    help = "Service JWT を発行して表示する（他サービス呼び出し・テスト用）"

    def add_arguments(self, parser):
        parser.add_argument(
            "scopes",
            nargs="*",
            default=["proposal.read"],
            help="付与するスコープ（省略時は proposal.read）",
        )
        parser.add_argument(
            "--service",
            default=None,
            help="発行元サービス名（省略時は settings.SERVICE_NAME）",
        )
        parser.add_argument(
            "--expires",
            type=int,
            default=3600,
            help="有効期限（秒）",
        )

    def handle(self, *args, **options):
        service_name = options["service"] or getattr(settings, "SERVICE_NAME", "root")
        secret = getattr(settings, "SERVICE_JWT_SECRET", "")
        if not secret:
            self.stderr.write(self.style.ERROR("SERVICE_JWT_SECRET が設定されていません。"))
            return
        scopes = options["scopes"]
        token = issue_jwt(
            service_name=service_name,
            scopes=scopes,
            secret=secret,
            expires_seconds=options["expires"],
        )
        self.stdout.write(token)
