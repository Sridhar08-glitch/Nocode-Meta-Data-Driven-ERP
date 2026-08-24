from django.urls import path

from . import views

app_name = "numbering"

urlpatterns = [
    path("sequences/", views.SequenceListCreateView.as_view(), name="sequence-list"),
    path("sequences/<uuid:seq_id>/", views.SequenceDetailView.as_view(), name="sequence-detail"),
    path("sequences/<uuid:seq_id>/peek/", views.SequencePeekView.as_view(), name="sequence-peek"),
    path("sequences/<uuid:seq_id>/allocate/", views.SequenceAllocateView.as_view(), name="sequence-allocate"),
    path("sequences/<uuid:seq_id>/reset/", views.SequenceResetView.as_view(), name="sequence-reset"),
    path("sequences/<uuid:seq_id>/allocations/", views.SequenceAllocationsView.as_view(), name="sequence-allocations"),
]
