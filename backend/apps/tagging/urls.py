from django.urls import path

from . import views

app_name = "tagging"

urlpatterns = [
    path("", views.TagListCreateView.as_view(), name="list-create"),
    path("records/", views.RecordTagsView.as_view(), name="record-tags"),
]
