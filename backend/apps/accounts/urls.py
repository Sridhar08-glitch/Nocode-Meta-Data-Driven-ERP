from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Password auth
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/mfa/", views.MfaLoginView.as_view(), name="login-mfa"),
    path("refresh/", views.RefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # Account self-service (Phase P2.17)
    path("resend-verification/", views.ResendVerificationView.as_view(), name="resend-verification"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("change-email/", views.ChangeEmailView.as_view(), name="change-email"),
    # Password reset
    path("password-reset/request/", views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    # MFA setup
    path("mfa/setup/initiate/", views.MfaSetupInitiateView.as_view(), name="mfa-setup-initiate"),
    path("mfa/setup/confirm/", views.MfaSetupConfirmView.as_view(), name="mfa-setup-confirm"),
    path("mfa/disable/", views.MfaDisableView.as_view(), name="mfa-disable"),
    # Sessions (Phase 1.27)
    path("sessions/", views.SessionListView.as_view(), name="session-list"),
    path("sessions/revoke-all/", views.SessionRevokeAllView.as_view(), name="session-revoke-all"),
    path("sessions/<uuid:family_id>/", views.SessionDetailView.as_view(), name="session-detail"),
    # Passkey / WebAuthn (Phase 1.27)
    path("mfa/passkey/register/begin/", views.PasskeyRegisterBeginView.as_view(),
         name="passkey-register-begin"),
    path("mfa/passkey/register/complete/", views.PasskeyRegisterCompleteView.as_view(),
         name="passkey-register-complete"),
    path("mfa/passkey/authenticate/begin/", views.PasskeyAuthenticateBeginView.as_view(),
         name="passkey-authenticate-begin"),
    path("mfa/passkey/authenticate/complete/", views.PasskeyAuthenticateCompleteView.as_view(),
         name="passkey-authenticate-complete"),
    path("mfa/passkey/", views.PasskeyListView.as_view(), name="passkey-list"),
    path("mfa/passkey/<str:credential_id>/", views.PasskeyDeleteView.as_view(), name="passkey-delete"),
    # Google OAuth2
    path("google/authorize/", views.GoogleAuthorizeView.as_view(), name="google-authorize"),
    path("google/callback/", views.GoogleCallbackView.as_view(), name="google-callback"),
    # Microsoft OAuth2
    path("microsoft/authorize/", views.MicrosoftAuthorizeView.as_view(), name="microsoft-authorize"),
    path("microsoft/callback/", views.MicrosoftCallbackView.as_view(), name="microsoft-callback"),
]
