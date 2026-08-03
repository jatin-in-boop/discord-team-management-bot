from typing import Optional


class BotError(Exception):
    """Base exception for all bot errors."""
    pass


class ConfigurationError(BotError):
    """Raised when configuration is invalid or missing."""
    pass


class DatabaseError(BotError):
    """Raised when a database operation fails."""
    pass


class PermissionError(BotError):
    """Raised when a user lacks required permissions."""
    pass
