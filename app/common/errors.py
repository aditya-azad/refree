class DatabaseEntryNotFoundError(Exception):
    """Raised when a requested database entry cannot be found."""

    def __init__(self, message: str = "") -> None:
        super().__init__(f"cannot find database entry: {message}")


class RepositoryError(Exception):
    """Raised when a repository operation fails.

    The message is safe to surface to the caller and does not expose
    sensitive details (e.g. connection strings, SQL, table names).
    The original exception is chained via ``__cause__`` and logged
    by the repository before this error is raised.
    """


class UsedAsForeignKeyError(Exception):
    """Raised when attempting to delete a row that is used as foreign key by another."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message or "row is a foreign key in another table")


class AnalyticsError(Exception):
    """Raised when an analytics event cannot be dispatched to the provider."""
