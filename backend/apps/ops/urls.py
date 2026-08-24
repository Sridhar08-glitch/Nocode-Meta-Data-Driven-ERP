from django.urls import path

from . import views

app_name = "ops"

urlpatterns = [
    path("healthz/", views.LivenessView.as_view(), name="liveness"),
    path("readyz/", views.ReadinessView.as_view(), name="readiness"),
]
