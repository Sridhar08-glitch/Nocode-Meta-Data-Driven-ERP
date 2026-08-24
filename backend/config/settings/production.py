from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa

DEBUG = False

# Fail fast: production must NOT run on the insecure dev-default secrets.
_INSECURE_DEFAULTS = {
    "DJANGO_SECRET_KEY": ("dev-secret-key-change-in-production", SECRET_KEY),  # noqa: F405
    "ENCRYPTION_KEY": ("nexus-dev-encryption-key-change-me", ENCRYPTION_KEY),  # noqa: F405
}
_unset = [name for name, (default, value) in _INSECURE_DEFAULTS.items() if not value or value == default]
if _unset:
    raise ImproperlyConfigured(
        f"Production requires non-default secrets: set {', '.join(_unset)} in the environment."
    )
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# TLS on by default in prod; flip to EMAIL_USE_SSL for implicit-TLS (port 465). Django rejects both.
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405 (env from `from .base import *`)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)  # noqa: F405

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
