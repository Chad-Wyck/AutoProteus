class Cancelled(Exception):
    """A host-controlled run was stopped."""


class IsolationError(ValueError):
    """Execution cannot proceed under the required isolation policy."""
