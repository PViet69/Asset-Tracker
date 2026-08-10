"""File embedding orchestration service."""

import logging
from dataclasses import dataclass
from typing import Sequence

from backend.app.api.schemas.file_embeddings import (
    FileEmbeddingItem,
    FileEmbeddingResponse,
)
from backend.app.exceptions import (
    FileProcessingError,
    ModelEndpointError,
    QdrantStorageError,
)
from backend.app.file_processing.service import process_file
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileUpload:
    """Immutable uploaded file value."""

    filename: str
    content_type: str
    content: bytes


class FileEmbeddingService:
    """Process files, create embeddings, and store vectors."""

    def __init__(self, model_client: ModelClient, qdrant_store: QdrantStore) -> None:
        self._model_client = model_client
        self._qdrant_store = qdrant_store

    def process_files(
        self, files: Sequence[FileUpload], model: str
    ) -> FileEmbeddingResponse:
        """Embed and store files, preserving input order."""
        items = [self._process_one(file, model) for file in files]
        return FileEmbeddingResponse(data=items)

    def startup(self) -> None:
        """Ensure embedding collection exists."""
        self._qdrant_store.ensure_collection()

    def _process_one(self, file: FileUpload, model: str) -> FileEmbeddingItem:
        try:
            processed = process_file(file.content, file.filename, file.content_type)
            if processed.kind == "text":
                vector = self._model_client.embed_text(str(processed.value), model)
            else:
                vector = self._model_client.embed_image(bytes(processed.value), model)
            self._qdrant_store.store_embedding(vector)
        except (FileProcessingError, ModelEndpointError, QdrantStorageError) as exc:
            return FileEmbeddingItem(
                filename=file.filename,
                content_type=file.content_type,
                error=exc.safe_message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "unexpected failure for %r (%s)",
                file.filename,
                type(exc).__name__,
            )
            return FileEmbeddingItem(
                filename=file.filename,
                content_type=file.content_type,
                error="Processing failed",
            )

        return FileEmbeddingItem(filename=file.filename, content_type=file.content_type)
