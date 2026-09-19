"""Domain exceptions raised by the service layer.
Services should NEVER raise HTTPException — they don't know they're
behind HTTP. Instead they raise these, and the API layer maps them.
This keeps services reusable (CLI, worker, GraphQL, etc.).
"""
class DomainError(Exception):
    """Base class for all domain errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
class NotFoundError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)
class ConflictError(DomainError):
    """Uniqueness / state conflicts — e.g., insufficient stock."""
    def __init__(self, message: str):
        super().__init__(message, status_code=409)
class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)
class AuthError(DomainError):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code=status_code)
class PermissionError_(DomainError):
    def __init__(self, message: str):
        super().__init__(message, status_code=403)