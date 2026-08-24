"""DRF serializers for authentication endpoints."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class _PasswordMixin(serializers.Serializer):
    """Shared password-strength validation using Django's validators."""

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class RegisterSerializer(_PasswordMixin):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(required=False, allow_blank=True, default="")


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class MfaLoginSerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    code = serializers.CharField()


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(_PasswordMixin):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ChangePasswordSerializer(_PasswordMixin):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    # Optional current refresh token — its session is preserved; all others are revoked.
    refresh = serializers.CharField(required=False, allow_blank=True)


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class MfaConfirmSerializer(serializers.Serializer):
    code = serializers.CharField()


class MfaDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)


# ── Sessions (Phase 1.27) ────────────────────────────────────────────────────
class SessionSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="family_id")
    user_agent = serializers.CharField()
    ip_address = serializers.IPAddressField(allow_null=True)
    created_at = serializers.DateTimeField()
    last_seen = serializers.DateTimeField(source="updated_at")
    expires_at = serializers.DateTimeField()


class RevokeAllSessionsSerializer(serializers.Serializer):
    # Optional current refresh token — its family is preserved (current-session aware).
    refresh = serializers.CharField(required=False, allow_blank=True)


# ── Passkey / WebAuthn (Phase 1.27) ──────────────────────────────────────────
class PasskeyRegisterCompleteSerializer(serializers.Serializer):
    credential = serializers.DictField()
    name = serializers.CharField(required=False, allow_blank=True, default="")


class PasskeyAuthenticateBeginSerializer(serializers.Serializer):
    mfa_token = serializers.CharField()


class PasskeyAuthenticateCompleteSerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    credential = serializers.DictField()
