"""Shared FastAPI dependencies."""

from backend.app.file_embeddings.service import FileEmbeddingService

_FILE_EMBEDDING_SERVICE: FileEmbeddingService | None = None


def get_file_embedding_service() -> FileEmbeddingService:
    """Return the configured file embedding service."""
    if _FILE_EMBEDDING_SERVICE is None:
        raise RuntimeError("File embedding service is not configured")
    return _FILE_EMBEDDING_SERVICE
