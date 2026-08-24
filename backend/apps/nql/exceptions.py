"""NQL error hierarchy — all user-facing query errors derive from NQLError."""


class NQLError(Exception):
    """Base class for all NQL parse/validation/compile errors."""


class NQLSyntaxError(NQLError):
    """Malformed NQL text or JSON AST."""


class UnknownFieldError(NQLError):
    """Reference to a field that does not exist on the entity."""


class UnknownOperatorError(NQLError):
    """Unsupported comparison operator."""


class UnknownEntityError(NQLError):
    """Reference to an entity that does not exist in the workspace."""


class NQLValueError(NQLError):
    """A value could not be coerced to the field's type."""
