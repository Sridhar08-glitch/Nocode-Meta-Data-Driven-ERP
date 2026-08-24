from django.urls import path

from . import views

app_name = "personalization"

urlpatterns = [
    path("appearance/", views.AppearanceView.as_view(), name="appearance"),
    path("preferences/", views.PreferencesView.as_view(), name="preferences"),
    path("preferences/reset/", views.PreferencesResetView.as_view(), name="preferences-reset"),
]
