from django.urls import path
from . import views

urlpatterns = [
    path("", views.ApprovalCreateView.as_view(), name="approval-create"),
]
