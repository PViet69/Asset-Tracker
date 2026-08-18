# Vector Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /v1/search` that embeds a text query and returns the most similar stored vectors from Qdrant, with image points carrying a payload (`filename`, `file_type`, `content`) so hits surface their stored description text.

**Architecture:** Image ingestion starts storing a Qdrant payload alongside the vector; text/PDF ingestion stays vector-only. The search route embeds the query through the existing `ModelClient`, queries Qdrant with a native `score_threshold` (no payload filter — all points searchable, payload-less hits map to `null` fields), and returns an OpenAI-style list envelope. Threshold comes from a new optional `SEARCH_THRESHOLD` setting; searching while it is unset returns 503.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, qdrant-client 1.19, pytest (markers `unit`/`integration`), uv.

**Spec:** `docs/superpowers/specs/2026-08-18-vector-search-design.md`

## Global Constraints

- **DO NOT COMMIT ANYTHING.** Every "Commit" step in this plan is deliberately replaced by "Stage changes for review". After all tasks finish, stop and let the user review the working tree (`git status` / `git diff`). Only the user decides when and what to commit.
- Threshold env var is named exactly `SEARCH_THRESHOLD` (no default; `float | None`).
- Payload keys exactly: `filename`, `file_type`, `content` (MIME stored under `file_type` — not `content_type`).
- No payload filter in search; payload-less/legacy points are never migrated.
- Reuse existing error patterns: `safe_message` exceptions, `QdrantStorageError("Qdrant storage failure")` wrapping, `SettingsError` for config problems.
- All new models immutable (`frozen=True` / frozen dataclasses).
- Tests run with `uv run pytest`; markers `@pytest.mark.unit` / `@pytest.mark.integration`.
- Route handlers stay synchronous (matches existing routes).

---

## File Map

| File | Action | Responsibility |
| --- | --- | --- |
| `backend/app/config.py` | Modify | `SEARCH_THRESHOLD` setting + range validation |
| `.env.example` | Modify | Document `SEARCH_THRESHOLD` |
| `backend/app/integrations/qdrant_store.py` | Modify | `store_embedding` gains payload param; new `SearchHit` + `search` |
| `backend/app/file_embeddings/ingestion_service.py` | Modify | Image payload construction; new `search` method |
| `backend/app/api/schemas/vector_search.py` | Create | Request/response models for `/v1/search` |
| `backend/app/api/routes/vector_search.py` | Create | `POST /v1/search` handler |
| `backend/app/api/routes/__init__.py` | Modify | Export new route module |
| `backend/app/main.py` | Modify | Register router, wire settings, protect path |
| `backend/tests/unit/test_qdrant_store.py` | Modify | Payload + search tests, config tests |
| `backend/tests/unit/test_ingestion_service.py` | Modify | Payload assertions + search tests |
| `backend/tests/integration/test_vector_search.py` | Create | Route integration tests |
| `README.md` | Modify | Search docs, config table, privacy rewrite |

---

### Task 1: `SEARCH_THRESHOLD` setting

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Test: `backend/tests/unit/test_qdrant_store.py` (existing settings tests live here)

**Interfaces:**
- Consumes: nothing
- Produces: `Settings.SEARCH_THRESHOLD: float | None` (default `None`); invalid values raise `pydantic.ValidationError` at construction

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_qdrant_store.py` (imports already present: `Settings`, `ValidationError`, `pytest`):

```python
@pytest.mark.unit
def test_search_threshold_defaults_to_none() -> None:
    settings = Settings(
        MODEL_ENDPOINT_URL="https://model.example",
        DESCRIPTION_MODEL="vision-model",
        DESCRIPTION_ENDPOINT_URL="https://vision.example",
        DESCRIPTION_ENDPOINT_API_KEY="vision-key",
        EMBEDDING_MODEL="embedding-model",
        QDRANT_URL="https://qdrant.example",
        QDRANT_VECTOR_SIZE=2,
    )

    assert settings.SEARCH_THRESHOLD is None


@pytest.mark.unit
def test_search_threshold_accepts_value_in_range() -> None:
    settings = Settings(
        MODEL_ENDPOINT_URL="https://model.example",
        DESCRIPTION_MODEL="vision-model",
        DESCRIPTION_ENDPOINT_URL="https://vision.example",
        DESCRIPTION_ENDPOINT_API_KEY="vision-key",
        EMBEDDING_MODEL="embedding-model",
        QDRANT_URL="https://qdrant.example",
        QDRANT_VECTOR_SIZE=2,
        SEARCH_THRESHOLD=0.5,
    )

    assert settings.SEARCH_THRESHOLD == 0.5


@pytest.mark.unit
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_search_threshold_outside_zero_one_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(
            MODEL_ENDPOINT_URL="https://model.example",
            DESCRIPTION_MODEL="vision-model",
            DESCRIPTION_ENDPOINT_URL="https://vision.example",
            DESCRIPTION_ENDPOINT_API_KEY="vision-key",
            EMBEDDING_MODEL="embedding-model",
            QDRANT_URL="https://qdrant.example",
            QDRANT_VECTOR_SIZE=2,
            SEARCH_THRESHOLD=value,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/test_qdrant_store.py -k search_threshold -v`
Expected: FAIL — `test_search_threshold_defaults_to_none` fails with `AttributeError: ... SEARCH_THRESHOLD`; parametrized test fails with `ValidationError: Extra inputs are not permitted`.

- [ ] **Step 3: Implement**

In `backend/app/config.py`, change the import line to:

```python
from pydantic import Field, StringConstraints, model_validator
```

Add the field after `QDRANT_DISTANCE: str = "Cosine"`:

```python
    SEARCH_THRESHOLD: float | None = Field(default=None, ge=0, le=1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_qdrant_store.py -v`
Expected: all PASS (no existing test regressions).

- [ ] **Step 5: Update `.env.example`**

Append at the end of `.env.example`:

```
# Required to use POST /v1/search. Minimum cosine similarity (0-1) for hits.
SEARCH_THRESHOLD=
```

- [ ] **Step 6: Stage changes for review — DO NOT COMMIT**

```bash
git add backend/app/config.py .env.example backend/tests/unit/test_qdrant_store.py
```

Leave staged. Do not run `git commit`.

---

### Task 2: Qdrant store — payload storage and `search`

**Files:**
- Modify: `backend/app/integrations/qdrant_store.py`
- Test: `backend/tests/unit/test_qdrant_store.py`

**Interfaces:**
- Consumes: none (Task 1 is config-only)
- Produces:
  - `store_embedding(embedding: list[float], payload: dict | None = None) -> str`
  - `SearchHit` frozen dataclass: `point_id: str`, `score: float`, `payload: dict`
  - `search(vector: list[float], limit: int, score_threshold: float) -> list[SearchHit]`
  - both new on `QdrantEmbeddingStore` and added to the `QdrantStore` protocol

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/test_qdrant_store.py`:

```python
@pytest.mark.unit
def test_store_embedding_upserts_point_with_payload() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )
    payload = {
        "filename": "photo.png",
        "file_type": "image/png",
        "content": "description text",
    }

    point_id = store.store_embedding([0.1, 0.2], payload=payload)

    UUID(point_id)
    point = client.upsert.call_args.kwargs["points"][0]
    assert point.vector == [0.1, 0.2]
    assert point.payload == payload
    client.upsert.assert_called_once_with(
        collection_name=COLLECTION,
        points=[point],
        wait=True,
    )


@pytest.mark.unit
def test_search_returns_hits_above_threshold() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )
    score_point = Mock()
    score_point.id = "point-1"
    score_point.score = 0.9
    score_point.payload = {
        "filename": "photo.png",
        "file_type": "image/png",
        "content": "description text",
    }
    client.query_points.return_value = Mock(points=[score_point])

    hits = store.search([0.1, 0.2], limit=5, score_threshold=0.4)

    client.query_points.assert_called_once_with(
        collection_name=COLLECTION,
        query=[0.1, 0.2],
        limit=5,
        score_threshold=0.4,
    )
    assert hits == [
        SearchHit(
            point_id="point-1",
            score=0.9,
            payload={
                "filename": "photo.png",
                "file_type": "image/png",
                "content": "description text",
            },
        )
    ]


@pytest.mark.unit
def test_search_without_payload_returns_empty_payload_dict() -> None:
    client = Mock()
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )
    score_point = Mock()
    score_point.id = "legacy-point"
    score_point.score = 0.8
    score_point.payload = None
    client.query_points.return_value = Mock(points=[score_point])

    hits = store.search([0.1, 0.2], limit=5, score_threshold=0.4)

    assert hits[0].payload == {}


@pytest.mark.unit
def test_search_failure_becomes_safe_chained_error() -> None:
    client = Mock()
    client.query_points.side_effect = RuntimeError("connection refused")
    store = QdrantEmbeddingStore.from_client(
        client,
        vector_size=2,
        collection=COLLECTION,
    )

    with pytest.raises(QdrantStorageError) as exc_info:
        store.search([0.1, 0.2], limit=5, score_threshold=0.4)

    assert exc_info.value.safe_message == "Qdrant storage failure"
    assert exc_info.value.__cause__ is not None
```

Add `SearchHit` to the existing qdrant_store import in the test file:

```python
from backend.app.integrations.qdrant_store import QdrantEmbeddingStore, SearchHit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/test_qdrant_store.py -k "payload or search" -v`
Expected: FAIL — `ImportError` for `SearchHit` (collection error), or assertion failures.

- [ ] **Step 3: Implement**

Rewrite `backend/app/integrations/qdrant_store.py`:

```python
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
    """One scored search result with its stored payload."""

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_qdrant_store.py -v`
Expected: all PASS, including the pre-existing `test_store_embedding_upserts_uuid_point_without_payload` (default `payload=None` keeps old behavior).

- [ ] **Step 5: Stage changes for review — DO NOT COMMIT**

```bash
git add backend/app/integrations/qdrant_store.py backend/tests/unit/test_qdrant_store.py
```

Leave staged. Do not run `git commit`.

---

### Task 3: Ingestion service — image payload and `search`

**Files:**
- Modify: `backend/app/file_embeddings/ingestion_service.py`
- Test: `backend/tests/unit/test_ingestion_service.py`

**Interfaces:**
- Consumes:
  - `store_embedding(embedding, payload=None)` (Task 2)
  - `store.search(vector, limit, score_threshold) -> list[SearchHit]` (Task 2)
  - `Settings.SEARCH_THRESHOLD` (Task 1)
- Produces:
  - Image ingestion stores payload `{"filename": str, "file_type": str, "content": str}`; text/PDF keeps `payload=None`
  - `FileIngestionService.__init__(..., settings: Settings | None = None)` — keyword arg, existing positional construction keeps working
  - `search(query: str, limit: int) -> VectorSearchResponse` (schema lands in Task 4; this task imports it — Task 4's schemas are the contract: `VectorSearchItem(point_id, score, filename, file_type, content)`, `VectorSearchResponse(data)` with default `object="list"`)
  - Raises `SettingsError("Search is not configured")` when threshold unset

**Note on ordering:** this task imports `VectorSearchResponse`/`VectorSearchItem` from `backend/app/api/schemas/vector_search.py`, which Task 4 creates. Execute Task 4 Step 1 (create the schema file) first if running tasks out of order, or run tasks in sequence 1→2→3→4 where Task 4's schema file is created before Task 3's tests run. To keep this plan runnable task-by-task in order, Task 4 Step 1 (schemas only) is split out as Task 3 Step 0 below.

- [ ] **Step 0: Create the response schema file (contract for this task)**

Create `backend/app/api/schemas/vector_search.py`:

```python
"""Vector search API schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DEFAULT_SEARCH_LIMIT = 10
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 100
MAX_SEARCH_QUERY_LENGTH = 8_192

SearchQuery = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_SEARCH_QUERY_LENGTH,
    ),
]


class VectorSearchRequest(BaseModel):
    """Validated vector search request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: SearchQuery
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT, ge=MIN_SEARCH_LIMIT, le=MAX_SEARCH_LIMIT
    )


class VectorSearchItem(BaseModel):
    """One public vector search result."""

    model_config = ConfigDict(frozen=True)

    point_id: str
    score: float
    filename: str | None = None
    file_type: str | None = None
    content: str | None = None


class VectorSearchResponse(BaseModel):
    """Vector search response envelope."""

    model_config = ConfigDict(frozen=True)

    object: Literal["list"] = "list"
    data: list[VectorSearchItem]
```

- [ ] **Step 1: Update existing image ingestion test (RED)**

In `backend/tests/unit/test_ingestion_service.py`, the existing test `test_image_description_text_is_embedded_and_only_vector_is_stored` asserts `qdrant_store.store_embedding.assert_called_once_with([0.3])`. Change that assertion to expect the payload:

```python
    qdrant_store.store_embedding.assert_called_once_with(
        [0.3],
        payload={
            "filename": "photo.png",
            "file_type": "image/png",
            "content": description.to_embedding_text(),
        },
    )
```

- [ ] **Step 2: Add new failing tests**

Append to `backend/tests/unit/test_ingestion_service.py`. Add these imports at the top:

```python
from backend.app.api.schemas.vector_search import VectorSearchResponse
from backend.app.config import Settings
from backend.app.exceptions import SettingsError
from backend.app.integrations.qdrant_store import SearchHit
```

(`FileProcessingError`, `ModelEndpointError`, `QdrantStorageError`, `Mock`, `patch`, `pytest`, `FileIngestionService`, `FileUpload`, `ProcessedInput`, `ImageDescription` are already imported.)

```python
def make_settings(search_threshold: float | None = 0.2) -> Settings:
    return Settings(
        _env_file=None,
        MODEL_ENDPOINT_URL="https://model.example",
        DESCRIPTION_MODEL="vision-model",
        DESCRIPTION_ENDPOINT_URL="https://vision.example",
        DESCRIPTION_ENDPOINT_API_KEY="vision-key",
        EMBEDDING_MODEL="embedding-model",
        QDRANT_URL="https://qdrant.example",
        QDRANT_VECTOR_SIZE=2,
        SEARCH_THRESHOLD=search_threshold,
    )


@pytest.mark.unit
def test_text_ingestion_stores_vector_without_payload() -> None:
    service, _, model_client, qdrant_store = make_service()
    model_client.embed_text.return_value = [0.5]
    upload = FileUpload("note.txt", "text/plain", b"hello world")

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        return_value=ProcessedInput("text", "hello world"),
    ):
        service.process_files((upload,))

    qdrant_store.store_embedding.assert_called_once_with([0.5], payload=None)


@pytest.mark.unit
def test_search_embeds_query_and_maps_hits() -> None:
    service, _, model_client, qdrant_store = make_service()
    service._settings = make_settings(0.2)
    model_client.embed_text.return_value = [0.7]
    qdrant_store.search.return_value = [
        SearchHit(
            point_id="point-1",
            score=0.9,
            payload={
                "filename": "photo.png",
                "file_type": "image/png",
                "content": "description text",
            },
        )
    ]

    response = service.search("red car", limit=5)

    model_client.embed_text.assert_called_once_with("red car")
    qdrant_store.search.assert_called_once_with([0.7], limit=5, score_threshold=0.2)
    assert response.model_dump() == {
        "object": "list",
        "data": [
            {
                "point_id": "point-1",
                "score": 0.9,
                "filename": "photo.png",
                "file_type": "image/png",
                "content": "description text",
            }
        ],
    }


@pytest.mark.unit
def test_search_without_configured_threshold_raises_settings_error() -> None:
    service, _, _, qdrant_store = make_service()

    with pytest.raises(SettingsError) as exc_info:
        service.search("red car", limit=5)

    assert exc_info.value.safe_message == "Search is not configured"
    qdrant_store.search.assert_not_called()


@pytest.mark.unit
def test_search_maps_missing_payload_fields_to_none() -> None:
    service, _, model_client, qdrant_store = make_service()
    service._settings = make_settings(0.2)
    model_client.embed_text.return_value = [0.7]
    qdrant_store.search.return_value = [
        SearchHit(point_id="legacy-1", score=0.6, payload={})
    ]

    response = service.search("red car", limit=5)

    assert response.data[0].model_dump() == {
        "point_id": "legacy-1",
        "score": 0.6,
        "filename": None,
        "file_type": None,
        "content": None,
    }
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest backend/tests/unit/test_ingestion_service.py -v`
Expected: FAIL — image payload assertion fails (current code passes no payload); new search tests fail with `AttributeError: ... search`.

- [ ] **Step 4: Implement**

In `backend/app/file_embeddings/ingestion_service.py`:

Add imports:

```python
from backend.app.api.schemas.vector_search import (
    VectorSearchItem,
    VectorSearchResponse,
)
from backend.app.config import Settings
from backend.app.exceptions import (
    FileProcessingError,
    ModelEndpointError,
    ModelNotFoundError,
    QdrantStorageError,
    SettingsError,
)
```

(replacing the existing `exceptions` import block).

Change the constructor:

```python
    def __init__(
        self,
        description_client: ImageDescriptionClient,
        model_client: ModelClient,
        qdrant_store: QdrantStore,
        settings: Settings | None = None,
    ) -> None:
        self._description_client = description_client
        self._model_client = model_client
        self._qdrant_store = qdrant_store
        self._settings = settings
```

Add after `embed_text`:

```python
    def search(self, query: str, limit: int) -> VectorSearchResponse:
        """Search stored vectors by embedded query text."""
        threshold = self._settings.SEARCH_THRESHOLD if self._settings else None
        if threshold is None:
            raise SettingsError("Search is not configured")
        vector = self._model_client.embed_text(query)
        hits = self._qdrant_store.search(vector, limit=limit, score_threshold=threshold)
        return VectorSearchResponse(data=[self._to_search_item(hit) for hit in hits])

    @staticmethod
    def _to_search_item(hit) -> VectorSearchItem:
        payload = hit.payload
        return VectorSearchItem(
            point_id=hit.point_id,
            score=hit.score,
            filename=payload.get("filename"),
            file_type=payload.get("file_type"),
            content=payload.get("content"),
        )
```

(Use `from backend.app.integrations.qdrant_store import QdrantStore, SearchHit` and annotate `hit: SearchHit`.)

In `_process_one`, replace:

```python
            vector = self._model_client.embed_text(embedding_text)
            self._qdrant_store.store_embedding(vector)
```

with:

```python
            vector = self._model_client.embed_text(embedding_text)
            payload = None
            if processed.kind == "image":
                payload = {
                    "filename": file.filename,
                    "file_type": file.content_type,
                    "content": embedding_text,
                }
            self._qdrant_store.store_embedding(vector, payload=payload)
```

(`embedding_text` is exactly the embedded description for images, so the payload content matches what was embedded. Text/PDF keeps `payload=None`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest backend/tests/unit/test_ingestion_service.py -v`
Expected: all PASS. Then run the whole suite to catch the other `store_embedding.assert_called_once_with([vector])` assertions in `backend/tests/integration/test_routes.py` (lines ~434, ~531) which now need `payload=None`:

Run: `uv run pytest backend/tests -v`

If `test_routes.py` integration tests fail on `store_embedding` assertions, update those two assertions to `assert_called_once_with([0.123456, -0.654321], payload=None)` and `assert_called_once_with([0.1, 0.2], payload=None)` respectively, and re-run until green.

- [ ] **Step 6: Stage changes for review — DO NOT COMMIT**

```bash
git add backend/app/api/schemas/vector_search.py \
        backend/app/file_embeddings/ingestion_service.py \
        backend/tests/unit/test_ingestion_service.py \
        backend/tests/integration/test_routes.py
```

Leave staged. Do not run `git commit`.

---

### Task 4: `/v1/search` route and wiring

**Files:**
- Create: `backend/app/api/routes/vector_search.py`
- Modify: `backend/app/api/routes/__init__.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_vector_search.py` (create)

**Interfaces:**
- Consumes: `VectorSearchRequest`/`VectorSearchResponse` schemas (Task 3 Step 0), `FileIngestionService.search` (Task 3), `require_upload_access` (existing)
- Produces: `POST /v1/search` behind bearer auth + rate limit; 503 when threshold unset; 503/502 for model errors; 502 for Qdrant errors

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/integration/test_vector_search.py`:

```python
"""Integration tests for the vector search route."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_file_ingestion_service
from backend.app.api.schemas.vector_search import (
    VectorSearchItem,
    VectorSearchResponse,
)
from backend.app.exceptions import (
    ModelEndpointError,
    ModelNotFoundError,
    QdrantStorageError,
    SettingsError,
)
from backend.app.file_embeddings.ingestion_service import FileIngestionService


def override_ingestion_service(app: FastAPI, service: Mock) -> None:
    app.dependency_overrides[get_file_ingestion_service] = lambda: service


def make_search_service() -> Mock:
    service = Mock(spec=FileIngestionService)
    service.embedding_model = "embedding-model"
    return service


@pytest.mark.integration
def test_search_returns_hits(app: FastAPI) -> None:
    service = make_search_service()
    service.search.return_value = VectorSearchResponse(
        data=[
            VectorSearchItem(
                point_id="point-1",
                score=0.9,
                filename="photo.png",
                file_type="image/png",
                content="description text",
            )
        ]
    )
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "point_id": "point-1",
                "score": 0.9,
                "filename": "photo.png",
                "file_type": "image/png",
                "content": "description text",
            }
        ],
    }
    service.search.assert_called_once_with("red car", limit=10)


@pytest.mark.integration
def test_search_passes_custom_limit(app: FastAPI) -> None:
    service = make_search_service()
    service.search.return_value = VectorSearchResponse(data=[])
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car", "limit": 3})

    assert response.status_code == 200
    assert response.json() == {"object": "list", "data": []}
    service.search.assert_called_once_with("red car", limit=3)


@pytest.mark.integration
@pytest.mark.parametrize("limit", [0, 101])
def test_search_rejects_limit_out_of_range(app: FastAPI, limit: int) -> None:
    service = make_search_service()
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car", "limit": limit})

    assert response.status_code == 422
    service.search.assert_not_called()


@pytest.mark.integration
def test_search_rejects_blank_query(app: FastAPI) -> None:
    service = make_search_service()
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "   "})

    assert response.status_code == 422
    service.search.assert_not_called()


@pytest.mark.integration
def test_search_returns_503_when_threshold_not_configured(app: FastAPI) -> None:
    service = make_search_service()
    service.search.side_effect = SettingsError("Search is not configured")
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Search is not configured"


@pytest.mark.integration
def test_search_returns_502_when_model_endpoint_fails(app: FastAPI) -> None:
    service = make_search_service()
    service.search.side_effect = ModelEndpointError("Model request failed")
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Model request failed"


@pytest.mark.integration
def test_search_returns_503_when_model_not_found(app: FastAPI) -> None:
    service = make_search_service()
    service.search.side_effect = ModelNotFoundError()
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Model not found"


@pytest.mark.integration
def test_search_returns_502_when_qdrant_fails(app: FastAPI) -> None:
    service = make_search_service()
    service.search.side_effect = QdrantStorageError("Qdrant storage failure")
    override_ingestion_service(app, service)

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Qdrant storage failure"


@pytest.mark.integration
def test_search_requires_bearer_token_when_upload_key_configured() -> None:
    from backend.app.main import create_app

    service = make_search_service()
    app = create_app(service=service, upload_api_key="secret-key")

    with TestClient(app) as client:
        response = client.post("/v1/search", json={"query": "red car"})

    assert response.status_code == 401
    service.search.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/integration/test_vector_search.py -v`
Expected: FAIL — 404/405 responses (route not registered yet) or import errors.

- [ ] **Step 3: Implement the route**

Create `backend/app/api/routes/vector_search.py`:

```python
"""Vector search API route."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.api.dependencies import get_file_ingestion_service
from backend.app.api.schemas.vector_search import (
    VectorSearchRequest,
    VectorSearchResponse,
)
from backend.app.exceptions import (
    ModelEndpointError,
    ModelNotFoundError,
    QdrantStorageError,
    SettingsError,
)
from backend.app.file_embeddings.ingestion_service import FileIngestionService
from backend.app.security import require_upload_access

router = APIRouter()


@router.post(
    "/v1/search",
    response_model=VectorSearchResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_upload_access)],
)
def search_vectors(
    payload: VectorSearchRequest,
    service: FileIngestionService = Depends(get_file_ingestion_service),
) -> VectorSearchResponse:
    """Search stored vectors by embedded query text."""
    try:
        return service.search(payload.query, limit=payload.limit)
    except SettingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.safe_message,
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.safe_message,
        ) from exc
    except ModelEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc
    except QdrantStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc
```

Update `backend/app/api/routes/__init__.py`:

```python
"""API route modules."""

from backend.app.api.routes import file_embeddings, health, vector_search

__all__ = ["file_embeddings", "health", "vector_search"]
```

- [ ] **Step 4: Wire into `backend/app/main.py`**

Add import next to the other route imports:

```python
from backend.app.api.routes.vector_search import (
    router as vector_search_router,
)
```

Register it after `text_embeddings_router`:

```python
    app.include_router(text_embeddings_router)
    app.include_router(vector_search_router)
```

Add `"/v1/search"` to the middleware's protected set so oversized-body rejection applies:

```python
        protected_paths = {"/v1/file-embeddings", "/v1/embeddings", "/v1/search"}
```

In the lifespan, pass settings into the service construction:

```python
            effective_service = FileIngestionService(
                description_client=description_client,
                model_client=model_client,
                qdrant_store=qdrant_store,
                settings=settings,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest backend/tests/integration/test_vector_search.py -v`
Expected: all PASS.

Then run the full suite:

Run: `uv run pytest -v`
Expected: all PASS. If `test_e2e_ingestion.py` assertions break (it constructs `FileIngestionService` with real fakes), only the image-payload expectation (`payload in (None, {})`) may need updating — check `backend/tests/integration/test_e2e_ingestion.py:108` and update to expect the image payload if that test ingests an image there; leave text expectations unchanged.

- [ ] **Step 6: Stage changes for review — DO NOT COMMIT**

```bash
git add backend/app/api/routes/vector_search.py \
        backend/app/api/routes/__init__.py \
        backend/app/main.py \
        backend/tests/integration/test_vector_search.py \
        backend/tests/integration/test_e2e_ingestion.py
```

Leave staged. Do not run `git commit`.

---

### Task 5: README documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: implemented endpoint behavior from Tasks 1–4
- Produces: accurate docs

- [ ] **Step 1: Add config table row**

In the Configuration table, add after the `QDRANT_DISTANCE` row:

```markdown
| `SEARCH_THRESHOLD` | No | None | Minimum cosine similarity (0–1) for `/v1/search` hits. Search is unavailable when unset. |
```

- [ ] **Step 2: Add the Vector search section**

Insert after the "Create text embeddings for vector search" section:

````markdown
## Vector search

`POST /v1/search` embeds the query text with the configured `EMBEDDING_MODEL` and returns stored vectors scoring at or above `SEARCH_THRESHOLD`, ordered by similarity. Image points carry a payload with the upload filename, MIME type, and stored description text; text/PDF points store no payload, so their `filename`, `file_type`, and `content` fields come back as `null`. Legacy points from before payloads existed behave the same way.

```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer $UPLOAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"a red sports car","limit":10}'
```

Response:

```json
{
  "object": "list",
  "data": [
    {
      "point_id": "3f2b...",
      "score": 0.87,
      "filename": "photo.png",
      "file_type": "image/png",
      "content": "Description text..."
    }
  ]
}
```

- `query` must be a single non-blank string (max 8192 characters).
- `limit` is optional, default 10, valid range 1–100.
- `SEARCH_THRESHOLD` must be set before calling this endpoint; when unset the endpoint returns HTTP 503 with `{"detail":"Search is not configured"}`.
- Requires the same bearer auth and rate limit as uploads.
````

- [ ] **Step 3: Rewrite the Privacy section**

Replace the current Privacy section with:

```markdown
## Privacy

- Image bytes leave the app only as part of the description request to `MODEL_ENDPOINT_URL`.
- Image descriptions are persisted as Qdrant point payloads (alongside the upload filename and MIME type) so search results can surface them.
- Text/PDF vectors are stored without payloads.
- API responses never expose raw vectors, API keys, tracebacks, or local paths.
```

Also remove the now-false sentence in the intro ("stores only the resulting vectors in Qdrant. Raw vectors and image descriptions are never returned.") — change it to:

```markdown
FastAPI service that accepts text, image, and PDF uploads, runs each image through a configurable vision-language model that returns a structured image description, embeds that description (or the raw text) via a configured text-embedding model, and stores the resulting vectors in Qdrant. Image points also store a payload with the filename, MIME type, and description text for vector search. Raw vectors are never returned.
```

- [ ] **Step 4: Verify docs render and match behavior**

Run: `uv run pytest -v` (sanity — docs change must not break tests).
Expected: all PASS.

- [ ] **Step 5: Stage changes for review — DO NOT COMMIT**

```bash
git add README.md
```

Leave staged. Do not run `git commit`.

---

### Final Step: Hand off for review — DO NOT COMMIT

- [ ] Show the user the full working-tree state:

```bash
git status
git diff --cached --stat
```

- [ ] Run the complete suite one last time:

```bash
uv run pytest -v
```

- [ ] Report: all tasks done, tests green, changes staged, **nothing committed** — waiting for user review.

---

## Plan Notes

- `SearchHit` is imported in `test_ingestion_service.py` — if you prefer the mapping tests not to depend on the store module, keep the import; it is part of the public store interface.
- The spec's error table maps `QdrantStorageError` → 502 and `ModelNotFoundError` → 503; Task 4 implements exactly that.
- No migration logic anywhere — payload-less points are simply returned with `null` payload fields when they match.
