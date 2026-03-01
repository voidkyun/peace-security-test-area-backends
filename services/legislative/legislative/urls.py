from django.urls import path

from . import views

urlpatterns = [
    path("laws/<str:law_id>/", views.LawDetailView.as_view(), name="law-detail"),
    path("lawsets/current/", views.LawsetCurrentView.as_view(), name="lawset-current"),
]
