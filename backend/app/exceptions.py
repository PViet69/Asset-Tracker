class SettingsError(Exception):
    """Raised when application settings are invalid or missing."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self._cause = cause

    @property
    def safe_message(self) -> str:
        """Public-facing error message without internal details."""
        return str(self)


class FileProcessingError(Exception):
    """Raised when file content cannot be processed."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self._cause = cause

    @property
    def safe_message(self) -> str:
        """Public-facing error message without internal details."""
        return str(self)


class ModelEndpointError(Exception):
    """Raised when the model endpoint request fails."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self._cause = cause

    @property
    def safe_message(self) -> str:
        """Public-facing error message without internal details."""
        return str(self)


class QdrantStorageError(Exception):
    """Raised when Qdrant storage operations fail."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self._cause = cause

    @property
    def safe_message(self) -> str:
        """Public-facing error message without internal details."""
        return str(self)
