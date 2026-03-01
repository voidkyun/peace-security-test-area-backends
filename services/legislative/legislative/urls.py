from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("laws/<str:law_id>/", views.LawDetailView.as_view(), name="law-detail"),
    path("lawsets/current/", views.LawsetCurrentView.as_view(), name="lawset-current"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
