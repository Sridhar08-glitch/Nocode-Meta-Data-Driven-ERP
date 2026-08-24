from django.urls import path

from . import views

app_name = "rules"

urlpatterns = [
    path("", views.RuleListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", views.RuleDetailView.as_view(), name="detail"),
]
