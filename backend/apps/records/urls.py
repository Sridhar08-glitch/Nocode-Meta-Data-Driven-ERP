from django.urls import path

from apps.activity import views as activity_views
from apps.sla import views as sla_views

from . import views

app_name = "records"

urlpatterns = [
    path("<slug:entity_slug>/", views.RecordListCreateView.as_view(), name="list-create"),
    path("<slug:entity_slug>/<uuid:record_id>/", views.RecordDetailView.as_view(), name="detail"),
    path("<slug:entity_slug>/<uuid:record_id>/restore/", views.RecordRestoreView.as_view(), name="restore"),
    path("<slug:entity_slug>/<uuid:record_id>/timeline/", views.RecordTimelineView.as_view(), name="timeline"),
    # Activity feed + comments (Phase 1.14)
    path("<slug:entity_slug>/<uuid:record_id>/activity/",
         activity_views.RecordActivityView.as_view(), name="record-activity"),
    path("<slug:entity_slug>/<uuid:record_id>/comments/",
         activity_views.RecordCommentsView.as_view(), name="record-comments"),
    path("<slug:entity_slug>/<uuid:record_id>/comments/<uuid:comment_id>/",
         activity_views.CommentDetailView.as_view(), name="comment-detail"),
    path("<slug:entity_slug>/<uuid:record_id>/comments/<uuid:comment_id>/pin/",
         activity_views.CommentPinView.as_view(), name="comment-pin"),
    path("<slug:entity_slug>/<uuid:record_id>/comments/<uuid:comment_id>/unpin/",
         activity_views.CommentUnpinView.as_view(), name="comment-unpin"),
    # SLA (Phase 1.19)
    path("<slug:entity_slug>/<uuid:record_id>/sla/",
         sla_views.RecordSLAView.as_view(), name="record-sla"),
    path("<slug:entity_slug>/<uuid:record_id>/sla/pause/",
         sla_views.RecordSLAPauseView.as_view(), name="record-sla-pause"),
    path("<slug:entity_slug>/<uuid:record_id>/sla/resume/",
         sla_views.RecordSLAResumeView.as_view(), name="record-sla-resume"),
]
