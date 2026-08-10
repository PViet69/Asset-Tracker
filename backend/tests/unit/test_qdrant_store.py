from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from pydantic import ValidationError
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.app.config import Settings
from backend.app.exceptions import QdrantStorageError
from backend.app.integrations.qdrant_store import QdrantEmbeddingStore

COLLECTION = "configured_embeddings"


@pytest.mark.unit
def test_settings_require_model_and_qdrant_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MODEL_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, QDRANT_VECTOR_SIZE=2)


@pytest.mark.unit
def test_constructs_client_once_from_settings() -> None:
    settings = Settings(
        MODEL_ENDPOINT_URL="https://model.example",
        QDRANT_URL="https://qdrant.example",
        QDRANT_API_KEY="secret-key",
        QDRANT_COLLECTION=COLLECTION,
        QDRANT_VECTOR_SIZE=2,
    )

    with patch("backend.app.integrations.qdrant_store.QdrantClient") as client_class:
        store = QdrantEmbeddingStore(settings)

    client_class.assert_called_once_with(
        url="https://qdrant.example",
        api_key="secret-key",
    )
    assert store.check_health() == "ok"
    client_class.return_value.get_collections.assert_called_once_with()


@pytest.mark.unit
def test_ensure_collection_creates_missing_configured_collection() -> None:
    client = Mock()
    client.collection_exists.return_value = False
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    store.ensure_collection()

    client.collection_exists.assert_called_once_with(collection_name=COLLECTION)
    client.create_collection.assert_called_once_with(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=2, distance=Distance.COSINE),
    )


@pytest.mark.unit
def test_ensure_collection_uses_configured_distance() -> None:
    settings = Settings(
        MODEL_ENDPOINT_URL="https://model.example",
        QDRANT_URL="https://qdrant.example",
        QDRANT_COLLECTION=COLLECTION,
        QDRANT_VECTOR_SIZE=2,
        QDRANT_DISTANCE="Dot",
    )

    with patch("backend.app.integrations.qdrant_store.QdrantClient") as client_class:
        client_class.return_value.collection_exists.return_value = False
        store = QdrantEmbeddingStore(settings)
        store.ensure_collection()

    client_class.return_value.create_collection.assert_called_once_with(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=2, distance=Distance.DOT),
    )


@pytest.mark.unit
def test_ensure_collection_does_not_create_existing_collection() -> None:
    client = Mock()
    client.collection_exists.return_value = True
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    store.ensure_collection()

    client.collection_exists.assert_called_once_with(collection_name=COLLECTION)
    client.create_collection.assert_not_called()


@pytest.mark.unit
def test_store_embedding_upserts_uuid_point_without_payload() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )
    embedding = [0.1, 0.2]

    point_id = store.store_embedding(embedding)

    assert str(UUID(point_id)) == point_id
    client.upsert.assert_called_once()
    request = client.upsert.call_args.kwargs
    assert request["collection_name"] == COLLECTION
    assert request["wait"] is True
    assert len(request["points"]) == 1
    point = request["points"][0]
    assert isinstance(point, PointStruct)
    assert point.id == point_id
    assert point.vector == embedding
    assert point.payload is None


@pytest.mark.unit
def test_ensure_collection_failure_becomes_safe_chained_error() -> None:
    client = Mock()
    failure = RuntimeError("secret client detail")
    client.collection_exists.side_effect = failure
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    with pytest.raises(QdrantStorageError) as exc_info:
        store.ensure_collection()

    assert str(exc_info.value) == "Qdrant storage failure"
    assert exc_info.value.__cause__ is failure


@pytest.mark.unit
def test_point_validation_failure_becomes_safe_chained_error() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )
    failure = ValueError("secret validation detail")

    with (
        patch(
            "backend.app.integrations.qdrant_store.PointStruct",
            side_effect=failure,
        ),
        pytest.raises(QdrantStorageError) as exc_info,
    ):
        store.store_embedding([0.1, 0.2])

    assert str(exc_info.value) == "Qdrant storage failure"
    assert exc_info.value.__cause__ is failure
    client.upsert.assert_not_called()


@pytest.mark.unit
def test_store_embedding_failure_becomes_safe_chained_error() -> None:
    client = Mock()
    failure = RuntimeError("secret client detail")
    client.upsert.side_effect = failure
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    with pytest.raises(QdrantStorageError) as exc_info:
        store.store_embedding([0.1, 0.2])

    assert str(exc_info.value) == "Qdrant storage failure"
    assert "secret client detail" not in str(exc_info.value)
    assert exc_info.value.__cause__ is failure


@pytest.mark.unit
def test_check_health_returns_ok() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    assert store.check_health() == "ok"
    client.get_collections.assert_called_once_with()


@pytest.mark.unit
def test_check_health_returns_unavailable_on_client_failure() -> None:
    client = Mock()
    client.get_collections.side_effect = RuntimeError("down")
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    assert store.check_health() == "unavailable"
