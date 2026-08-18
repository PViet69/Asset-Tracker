"""Shared FastAPI dependencies."""

from backend.app.file_embeddings.ingestion_service import FileIngestionService

_FILE_INGESTION_SERVICE: FileIngestionService | None = None


def get_file_ingestion_service() -> FileIngestionService:
    """Return configured file ingestion service."""
    if _FILE_INGESTION_SERVICE is None:
        raise RuntimeError("File ingestion service is not configured")
    return _FILE_INGESTION_SERVICE
