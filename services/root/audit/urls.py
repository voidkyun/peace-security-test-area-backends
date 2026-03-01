from django.urls import path
from . import views

urlpatterns = [
    path("events/", views.AuditEventListCreateView.as_view(), name="audit-event-list"),
    path("events/<int:pk>/", views.AuditEventDetailView.as_view(), name="audit-event-detail"),
]
