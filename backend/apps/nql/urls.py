from django.urls import path

from . import views

app_name = "nql"

urlpatterns = [
    path("query/", views.NQLQueryView.as_view(), name="query"),
]
