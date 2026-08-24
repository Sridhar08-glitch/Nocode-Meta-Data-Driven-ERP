"""Sridhar ERP base settings."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-secret-key-change-in-production")
DEBUG = env("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "channels",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.tenancy",
    "apps.admin_views",
    "apps.metadata",
    "apps.physical_tables",
    "apps.schema_registry",
    "apps.records",
    "apps.relationships",
    "apps.eventstore",
    "apps.projections",
    "apps.nql",
    "apps.permissions",
    "apps.workflows",
    "apps.lineage",
    "apps.config_vcs",
    "apps.marketplace",
    "apps.backups",
    "apps.notifications",
    "apps.reporting",
    "apps.search",
    "apps.documents",
    "apps.integrations",
    "apps.audit",
    "apps.rules",
    "apps.computed",
    "apps.approvals",
    "apps.sla",
    "apps.recyclebin",
    "apps.staging",
    "apps.activity",
    "apps.tagging",
    "apps.views_saved",
    "apps.public_forms",
    "apps.portal",
    "apps.localization",
    "apps.branding",
    "apps.feature_flags",
    "apps.personalization",
    "apps.realtime",
    "apps.studio",
    "apps.email_templates",
    "apps.document_templates",
    "apps.process_catalog",
    "apps.ops",
    "apps.numbering",
    "apps.companies",
    "apps.currency",
    "apps.dimensions",
    "apps.ledger",
    "apps.consolidation",
    "apps.inventory",
    "apps.solution_templates",
    "apps.procurement",
    "apps.crm",
    "apps.hr",
    "apps.payroll",
    "apps.assets",
    "apps.projects",
    "apps.helpdesk",
    "apps.manufacturing",
    "apps.analytics",
    "apps.dependency",
    "apps.environments",
    "apps.certification",
    "apps.packaging",
    "apps.guards",
    "apps.aggregation",
    "apps.credits",
    "apps.collections_engine",
    "apps.taxes",
    "apps.revenue",
    "apps.financial_reports",
    "apps.settlement",
    "apps.cash",
    "apps.budgets",
    "apps.treasury",
    "apps.financial_kpis",
    "apps.system_entities",
    "apps.school",
    "apps.college",
    "apps.university",
    "apps.hospital",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.ops.middleware.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.tenancy.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://nexus:nexus@localhost:5432/nexus_dev")
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["OPTIONS"] = {"options": "-c search_path=public"}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# bcrypt (≥12 rounds, Django's BCryptSHA256 default) is the primary hasher (§7.1);
# PBKDF2 kept as a fallback so any pre-existing hashes still verify.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

PROJECT_ROOT = BASE_DIR.parent

JWT_PRIVATE_KEY_PATH = env("JWT_PRIVATE_KEY_PATH", default="keys/jwt_private.pem")
JWT_PUBLIC_KEY_PATH  = env("JWT_PUBLIC_KEY_PATH",  default="keys/jwt_public.pem")

def _read_key(path):
    # Relative key paths resolve against the project root (E:\erp), not the cwd,
    # so tokens sign correctly regardless of where the process is launched from.
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    try:
        with open(p) as f:
            return f.read()
    except FileNotFoundError:
        return None

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "RS256",
    "SIGNING_KEY": _read_key(JWT_PRIVATE_KEY_PATH),
    "VERIFYING_KEY": _read_key(JWT_PUBLIC_KEY_PATH),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.NexusJWTAuthentication",
        "apps.accounts.authentication.ApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.NexusCursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.nexus_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Sridhar ERP API",
    "DESCRIPTION": "No-Code Enterprise Operating System",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ["accept", "authorization", "content-type", "origin", "x-workspace-slug", "x-request-id"]

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Symmetric key used to encrypt at-rest secrets (e.g. TOTP MFA secrets).
# A passphrase is acceptable — crypto.get_fernet() derives a valid Fernet key from it.
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="nexus-dev-encryption-key-change-me")

# Google OAuth2 (env uses the GOOGLE_OAUTH_ prefix; fall back to the legacy names).
GOOGLE_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default=env("GOOGLE_CLIENT_ID", default=""))
GOOGLE_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default=env("GOOGLE_CLIENT_SECRET", default=""))
GOOGLE_OAUTH_REDIRECT_URI = env(
    "GOOGLE_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/api/v1/auth/google/callback/",
)

# Microsoft OAuth2 (Azure AD v2.0).
MICROSOFT_CLIENT_ID = env("MICROSOFT_OAUTH_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = env("MICROSOFT_OAUTH_CLIENT_SECRET", default="")
MICROSOFT_OAUTH_REDIRECT_URI = env(
    "MICROSOFT_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/api/v1/auth/microsoft/callback/",
)
MICROSOFT_OAUTH_TENANT = env("MICROSOFT_OAUTH_TENANT", default="common")

# Progressive login lockout: N failures within the window → temporary lock (§7.2).
LOGIN_LOCKOUT_ENABLED = env.bool("LOGIN_LOCKOUT_ENABLED", default=True)
LOGIN_LOCKOUT_THRESHOLD = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 minutes

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
# Authenticated SMTP credentials (wired from env so the production SMTP backend can log in).
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@nexuserp.local")
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# PDF rendering (Phase 1.31). "reportlab" = pure-Python (no system libs, default);
# "weasyprint" = HTML/CSS → PDF, requires the GTK/pango/cairo runtime on the host.
NEXUS_PDF_BACKEND = env("NEXUS_PDF_BACKEND", default="reportlab")

# WebAuthn / Passkey (Phase 1.27)
WEBAUTHN_RP_ID = env("WEBAUTHN_RP_ID", default="localhost")
WEBAUTHN_RP_NAME = env("WEBAUTHN_RP_NAME", default="Sridhar ERP")
WEBAUTHN_ORIGIN = env("WEBAUTHN_ORIGIN", default=FRONTEND_URL)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "nexus": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# Sridhar ERP knobs
NEXUS_MAX_FIELDS_PER_ENTITY = 500
NEXUS_MAX_ENTITIES_PER_WORKSPACE = 200
NEXUS_NQL_MAX_LIMIT = 10000
NEXUS_FORMULA_TIMEOUT_MS = 5000

# ── Observability (Phase P1.6) ───────────────────────────────────────────────
# Sentry is OPTIONAL and entirely env-gated: error/performance reporting activates only
# when SENTRY_DSN is set AND the `sentry-sdk` package is installed. With no DSN (the default
# for dev/CI/tests) this is a complete no-op, so the suite never touches the network.
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
SENTRY_RELEASE = env("SENTRY_RELEASE", default="")

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            release=SENTRY_RELEASE or None,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            # Never let request bodies (which may carry secrets) reach Sentry by default.
            send_default_pii=False,
        )
    except ImportError:
        import logging

        logging.getLogger("nexus").warning(
            "SENTRY_DSN is set but the 'sentry-sdk' package is not installed; "
            "error reporting is disabled. Run: pip install sentry-sdk"
        )
