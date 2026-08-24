from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("setup/", views.SetupView.as_view(), name="setup"),
    path("leads/<uuid:record_id>/qualify/", views.LeadQualifyView.as_view(), name="qualify_lead"),
    path("opportunities/<uuid:record_id>/win/",
         views.OpportunityWinView.as_view(), name="win_opportunity"),
    path("opportunities/<uuid:record_id>/lose/",
         views.OpportunityLoseView.as_view(), name="lose_opportunity"),
    path("activities/<uuid:record_id>/complete/",
         views.ActivityCompleteView.as_view(), name="complete_activity"),
    path("<slug:entity_slug>/", views.DocumentCreateView.as_view(), name="create_document"),
]
