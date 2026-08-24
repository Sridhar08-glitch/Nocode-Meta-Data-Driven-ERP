from django.urls import path

from . import views

app_name = "views_saved"

urlpatterns = [
    path("", views.SavedViewListCreateView.as_view(), name="list-create"),
    path("<uuid:view_id>/", views.SavedViewDetailView.as_view(), name="detail"),
]
