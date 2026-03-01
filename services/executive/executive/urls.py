from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from exec import views as exec_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("evaluations/", exec_views.EvaluationCreateView.as_view(), name="evaluation-create"),
    path("exec/proposals/", exec_views.ExecProposalCreateView.as_view(), name="exec-proposal-create"),
    path("exec/proposals/<uuid:id>/finalize/", exec_views.ExecProposalFinalizeView.as_view(), name="exec-proposal-finalize"),
]
