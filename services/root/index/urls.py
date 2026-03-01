from django.urls import path
from . import views

urlpatterns = [
    path("entries/", views.IndexEntryListCreateView.as_view(), name="index-entry-list"),
    path(
        "entries/<uuid:proposal_id>/",
        views.IndexEntryDetailView.as_view(),
        name="index-entry-detail",
    ),
]
