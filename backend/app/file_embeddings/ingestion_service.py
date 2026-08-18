"""File ingestion orchestration for one shared text embedding space."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.api.schemas.file_embeddings import (
    FileEmbeddingItem,
    FileEmbeddingResponse,
)
from backend.app.exceptions import (
    FileProcessingError,
    ModelEndpointError,
    ModelNotFoundError,
    QdrantStorageError,
)
from backend.app.file_processing.service import process_file
from backend.app.file_processing.types import ProcessedInput
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore
from backend.app.model.description_client import ImageDescriptionClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileUpload:
    """Immutable uploaded file value."""

    filename: str
    content_type: str
    content: bytes


class FileIngestionService:
    """Convert files to text embeddings and store only vectors."""

    def __init__(
        self,
        description_client: ImageDescriptionClient,
        model_client: ModelClient,
        qdrant_store: QdrantStore,
    ) -> None:
        self._description_client = description_client
        self._model_client = model_client
        self._qdrant_store = qdrant_store

    @property
    def embedding_model(self) -> str:
        """Return configured embedding model identifier."""
        return self._model_client.model_name

    def process_files(
        self,
        files: Sequence[FileUpload],
    ) -> FileEmbeddingResponse:
        """Ingest files independently while preserving input order."""
        return FileEmbeddingResponse(data=[self._process_one(file) for file in files])

    def startup(self) -> None:
        """Ensure embedding collection exists."""
        self._qdrant_store.ensure_collection()

    def embed_text(self, text: str) -> list[float]:
        """Embed query text without storing it."""
        return self._model_client.embed_text(text)

    def _process_one(self, file: FileUpload) -> FileEmbeddingItem:
        try:
            processed = process_file(
                file.content,
                file.filename,
                file.content_type,
            )
            embedding_text = self._to_embedding_text(processed)
            vector = self._model_client.embed_text(embedding_text)
            self._qdrant_store.store_embedding(vector)
        except ModelNotFoundError:
            raise
        except (FileProcessingError, ModelEndpointError, QdrantStorageError) as exc:
            return FileEmbeddingItem(
                filename=file.filename,
                content_type=file.content_type,
                status="failed",
                reason=exc.safe_message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected ingestion failure for %r (%s)",
                file.filename,
                type(exc).__name__,
            )
            return FileEmbeddingItem(
                filename=file.filename,
                content_type=file.content_type,
                status="failed",
                reason="Processing failed",
            )

        return FileEmbeddingItem(
            filename=file.filename,
            content_type=file.content_type,
            status="success",
            reason=None,
        )

    def _to_embedding_text(self, processed: ProcessedInput) -> str:
        if processed.kind == "text":
            return str(processed.value)
        description = self._description_client.describe(bytes(processed.value))
        return description.to_embedding_text()
