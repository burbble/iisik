class DomainError(Exception):
    """Base domain error."""


class NotFoundError(DomainError):
    """Requested business object was not found."""


class ValidationError(DomainError):
    """Input data violates a business rule."""


class ConflictError(DomainError):
    """Operation conflicts with the current object state."""


class AuthenticationError(DomainError):
    """Request is not authenticated or the session is no longer active."""


class AuthorizationError(DomainError):
    """Authenticated user does not have access to an operation."""
