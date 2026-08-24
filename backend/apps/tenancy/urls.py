from django.urls import path

from . import views

app_name = "tenancy"

urlpatterns = [
    # GET = my workspaces, POST = create a workspace (self-service onboarding)
    path("", views.MyWorkspacesView.as_view(), name="my-workspaces"),

    # Invitation accept/reject by token (invitee may not be a member yet — no slug)
    path("invitations/accept/", views.InvitationAcceptView.as_view(), name="invitation-accept"),
    path("invitations/reject/", views.InvitationRejectView.as_view(), name="invitation-reject"),

    # Workspace-scoped invitations (admin)
    path("<slug:slug>/invitations/<uuid:invitation_id>/resend/",
         views.InvitationResendView.as_view(), name="invitation-resend"),
    path("<slug:slug>/invitations/<uuid:invitation_id>/cancel/",
         views.InvitationCancelView.as_view(), name="invitation-cancel"),
    path("<slug:slug>/invitations/", views.InvitationListCreateView.as_view(),
         name="invitation-list"),

    # Member management (most specific first)
    path("<slug:slug>/members/<uuid:member_id>/suspend/",
         views.MemberSuspendView.as_view(), name="member-suspend"),
    path("<slug:slug>/members/<uuid:member_id>/reactivate/",
         views.MemberReactivateView.as_view(), name="member-reactivate"),
    path("<slug:slug>/members/<uuid:member_id>/reset-password/",
         views.MemberResetPasswordView.as_view(), name="member-reset-password"),
    path("<slug:slug>/members/<uuid:member_id>/",
         views.MemberDetailView.as_view(), name="member-detail"),
    path("<slug:slug>/members/", views.MemberListView.as_view(), name="member-list"),

    # Workspace administration
    path("<slug:slug>/transfer-ownership/",
         views.WorkspaceTransferOwnershipView.as_view(), name="transfer-ownership"),
    path("<slug:slug>/archive/", views.WorkspaceArchiveView.as_view(), name="workspace-archive"),
    path("<slug:slug>/restore/", views.WorkspaceRestoreView.as_view(), name="workspace-restore"),
    path("<slug:slug>/delete-permanently/confirm/",
         views.WorkspaceHardDeleteConfirmView.as_view(), name="workspace-hard-delete-confirm"),
    path("<slug:slug>/delete-permanently/",
         views.WorkspaceHardDeleteRequestView.as_view(), name="workspace-hard-delete"),
    path("<slug:slug>/", views.WorkspaceDetailView.as_view(), name="workspace-detail"),
]
