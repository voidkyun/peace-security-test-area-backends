from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.RootView.as_view()),
    path("internal/example/", views.InternalExampleView.as_view()),
    path("audit/", include("audit.urls")),
    path("index/", include("index.urls")),
    # OpenAPI スキーマ・Swagger UI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
