from django.urls import path

from . import views

app_name = "relationships"

urlpatterns = [
    path("", views.RelationshipListCreateView.as_view(), name="list"),
    path("<uuid:relationship_id>/", views.RelationshipDetailView.as_view(), name="detail"),
    path("<uuid:relationship_id>/links/", views.RelationshipLinkView.as_view(), name="links"),
]
