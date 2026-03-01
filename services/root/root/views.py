"""Root サービス用ビュー（公開窓口）。"""
from django.http import HttpResponse


def root(request):
    """トップパス: サービス稼働確認用。"""
    return HttpResponse("Root service is running.", content_type="text/plain; charset=utf-8")
