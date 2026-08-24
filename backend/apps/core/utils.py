"""Shared utilities."""
import hashlib
import secrets
import uuid

from django.utils import timezone


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


def generate_token(nbytes=32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_short_id(prefix="") -> str:
    """Generate a short random ID (e.g. for API keys)."""
    raw = secrets.token_hex(8)
    return f"{prefix}{raw}" if prefix else raw


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def now():
    return timezone.now()


def snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def camel_to_snake(name: str) -> str:
    import re
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def safe_table_name(raw: str) -> str:
    """Sanitize a string for use as a PostgreSQL table name."""
    import re
    cleaned = re.sub(r"[^a-z0-9_]", "_", raw.lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned and cleaned[0].isdigit():
        cleaned = "t_" + cleaned
    return cleaned[:63]  # PostgreSQL identifier limit
