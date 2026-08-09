"""Domain-specific exceptions for PIE."""


class PieError(Exception):
    """Base exception for all PIE related errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PieAuthError(PieError):
    """Raised when authentication with Microsoft Entra ID or Azure Identity fails."""
    pass


class PiePermissionError(PieError):
    """Raised when the required Azure RBAC role (e.g., Reader) is missing."""
    pass


class PieDiscoveryError(PieError):
    """Raised during Azure resource or metadata discovery failures."""
    pass


class PieResourceNotFoundError(PieError):
    """Raised when an Azure Data Factory, Subscription, or Resource Group is not found."""
    pass


class PieConfigError(PieError):
    """Raised when configuration parameters are invalid or missing."""
    pass
