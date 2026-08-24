"""
Schema Registry exceptions.

All exceptions raised by SchemaRegistryService live here so callers
can import just what they need without touching the service module.
"""


class SchemaRegistryError(Exception):
    """Base class for all schema registry errors."""


class EntityAlreadyExistsError(SchemaRegistryError):
    """Raised when an entity with the same workspace + slug already exists."""


class EntityNotFoundError(SchemaRegistryError):
    """Raised when an entity cannot be found."""


class FieldAlreadyExistsError(SchemaRegistryError):
    """Raised when a field with the same slug already exists on the entity."""


class FieldNotFoundError(SchemaRegistryError):
    """Raised when a field definition cannot be found."""


class InvalidSlugError(SchemaRegistryError):
    """Raised when a slug does not match the required format."""


class InvalidFieldTypeError(SchemaRegistryError):
    """Raised when an unrecognised field_type is supplied."""


class SystemFieldError(SchemaRegistryError):
    """Raised when a caller attempts to mutate a system-managed field."""


class SchemaVersionNotFoundError(SchemaRegistryError):
    """Raised when a requested schema version number does not exist."""


class RollbackError(SchemaRegistryError):
    """Raised when a schema rollback cannot be completed."""
