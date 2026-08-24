"""Workspace membership emails (kept separate so the service stays I/O-light)."""
from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


def send_member_invite_email(workspace, user, role, *, set_password_token=None) -> None:
    """Tell a seated member they now have access. New accounts get a set-password
    link (a password-reset token) so they can sign in for the first time."""
    if set_password_token:
        link = f"{settings.FRONTEND_URL}/reset-password?token={set_password_token}"
        body = (
            f"You've been added to the {workspace.name} workspace on Sridhar ERP "
            f"as {role}.\n\nSet your password to sign in:\n\n{link}\n\n"
            f"This link expires in 1 hour."
        )
    else:
        link = f"{settings.FRONTEND_URL}/login"
        body = (
            f"You've been added to the {workspace.name} workspace on Sridhar ERP "
            f"as {role}.\n\nSign in:\n\n{link}"
        )
    send_mail(
        subject=f"You've been added to {workspace.name} on Sridhar ERP",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def send_invitation_email(workspace, email, role, raw_token) -> None:
    """Pending-invitation email — the recipient accepts via the tokenised link
    (registering/signing in first if they have no account yet)."""
    link = f"{settings.FRONTEND_URL}/invite/accept?token={raw_token}"
    send_mail(
        subject=f"You're invited to {workspace.name} on Sridhar ERP",
        message=(
            f"You've been invited to join the {workspace.name} workspace as {role}.\n\n"
            f"Accept the invitation:\n\n{link}\n\n"
            f"If you don't have a Sridhar ERP account yet, sign up with this email first, "
            f"then open the link. This invitation expires in 7 days."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
