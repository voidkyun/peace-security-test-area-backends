from django.urls import path
from . import views

urlpatterns = [
    path("", views.ApprovalListCreateView.as_view(), name="approval-list"),
]
