from django.urls import path

from . import views

app_name = "admin_views"

urlpatterns = [
    path("health/", views.TenantHealthView.as_view(), name="health"),
]
