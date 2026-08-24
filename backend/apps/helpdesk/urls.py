from django.urls import path

from . import views as v

app_name = "helpdesk"

urlpatterns = [
    path("setup/", v.SetupView.as_view(), name="setup"),
    path("tickets/<uuid:pk>/assign/", v.TicketAssign.as_view(), name="ticket_assign"),
    path("tickets/<uuid:pk>/auto-assign/", v.TicketAutoAssign.as_view(), name="ticket_auto_assign"),
    path("tickets/<uuid:pk>/escalate/", v.TicketEscalate.as_view(), name="ticket_escalate"),
    path("tickets/<uuid:pk>/status/", v.TicketStatus.as_view(), name="ticket_status"),
    path("tickets/<uuid:pk>/resolve/", v.TicketResolve.as_view(), name="ticket_resolve"),
    path("tickets/<uuid:pk>/close/", v.TicketClose.as_view(), name="ticket_close"),
    path("tickets/<uuid:pk>/csat/", v.TicketCsat.as_view(), name="ticket_csat"),
    path("changes/<uuid:pk>/approve/", v.ChangeApprove.as_view(), name="change_approve"),
    path("knowledge/recommend/", v.KnowledgeRecommend.as_view(), name="knowledge_recommend"),
    path("sla/dashboard/", v.SlaDashboard.as_view(), name="sla_dashboard"),
    path("<slug:entity_slug>/", v.DocumentCreate.as_view(), name="create_document"),
]
