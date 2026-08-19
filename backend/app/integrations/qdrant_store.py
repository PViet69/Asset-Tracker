"""Qdrant adapter for storing and searching file embedding vectors."""

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.app.config import Settings
from backend.app.exceptions import QdrantStorageError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    """One scored vector search result with its stored payload."""

    point_id: str
    score: float
    payload: dict


class QdrantStore(Protocol):
    """Protocol for Qdrant collection, storage, search, and health operations."""

    def ensure_collection(self) -> None: ...
    def store_embedding(
        self, embedding: list[float], payload: dict | None = None
    ) -> str: ...
    def search(
        self, vector: list[float], limit: int, score_threshold: float
    ) -> list[SearchHit]: ...
    def check_health(self) -> str: ...


class QdrantEmbeddingStore:
    """Store and search embedding vectors in a configured Qdrant collection."""

    def __init__(self, settings: Settings) -> None:
        self._client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        self._vector_size = settings.QDRANT_VECTOR_SIZE
        self._collection = settings.QDRANT_COLLECTION
        self._distance = Distance(settings.QDRANT_DISTANCE)

    @classmethod
    def from_client(
        cls,
        client: QdrantClient,
        vector_size: int,
        collection: str,
    ) -> "QdrantEmbeddingStore":
        """Construct with a pre-built Qdrant client for testing."""
        instance = cls.__new__(cls)
        instance._client = client
        instance._vector_size = vector_size
        instance._collection = collection
        instance._distance = Distance.COSINE
        return instance

    def ensure_collection(self) -> None:
        """Create configured collection when it does not exist."""
        try:
            if self._client.collection_exists(collection_name=self._collection):
                return
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=self._distance,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant collection operation failed", exc_info=True)
            raise QdrantStorageError("Qdrant storage failure") from exc

    def store_embedding(
        self, embedding: list[float], payload: dict | None = None
    ) -> str:
        """Upsert one embedding point and return its generated UUID."""
        point_id = str(uuid4())
        try:
            point = PointStruct(id=point_id, vector=embedding, payload=payload)
            self._client.upsert(
                collection_name=self._collection,
                points=[point],
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant embedding upsert failed", exc_info=True)
            raise QdrantStorageError("Qdrant storage failure") from exc
        return point_id

    def search(
        self, vector: list[float], limit: int, score_threshold: float
    ) -> list[SearchHit]:
        """Return top scored points at or above score_threshold."""
        try:
            points = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=limit,
                score_threshold=score_threshold,
            ).points
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant search failed", exc_info=True)
            raise QdrantStorageError("Qdrant storage failure") from exc
        return [
            SearchHit(
                point_id=str(point.id),
                score=point.score,
                payload=point.payload or {},
            )
            for point in points
        ]

    def check_health(self) -> str:
        """Return Qdrant availability without exposing client errors."""
        try:
            self._client.get_collections()
        except Exception:  # noqa: BLE001
            return "unavailable"
        return "ok"
