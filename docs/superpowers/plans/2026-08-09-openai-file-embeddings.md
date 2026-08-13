# OpenAI File Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only FastAPI service that accepts text, image, and PDF uploads, creates one embedding per successful file through an OpenAI-compatible model endpoint, stores vectors in Qdrant, and returns per-file results.

**Architecture:** Use a small `backend/app` package with thin synchronous FastAPI routes, typed Pydantic schemas, a file-processing module, a model-client adapter, a Qdrant adapter, and one orchestration service. Synchronous routes keep implementation simple: FastAPI executes regular `def` handlers in its worker pool, while file parsers and sync SDK clients remain ordinary synchronous code. Process each file independently so one failure does not discard successful files.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic Settings, python-magic, Pillow, pypdf, OpenAI Python SDK, Qdrant client, pytest, pytest-cov, httpx.

## Global Constraints

- `POST /v1/file-embeddings` accepts multipart form data with one or more `files` fields and a `model` field.
- `GET /health` reports process, Qdrant, and external model status.
- Supported file groups: text, PNG/JPEG/WEBP images, and PDFs.
- File type detection uses MIME content from `python-magic`; extension is not used for detection.
- Max files per request is 10.
- Max file size is 25 MB.
- Empty files are rejected.
- Unsupported file types receive per-file errors.
- PDFs use text extraction only; scanned PDF OCR is out of scope.
- One embedding and one UUID Qdrant point are created per successful uploaded file.
- Qdrant collection defaults to `file_embeddings`; distance defaults to cosine.
- Model and Qdrant URLs/API keys come from environment variables; no secrets are hardcoded.
- Raw embedding vectors are never returned to callers.
- No frontend, search endpoint, authentication, or background queue is included.
- Service and integration modules do not import FastAPI; HTTP mapping stays in routes or exception handlers.
- Every function signature has Python type annotations; DTOs use Pydantic models rather than untyped dictionaries.
- Tests use pytest and must reach at least 80% coverage for `backend/app`.

---

## File Map

### Create

- `pyproject.toml` — package metadata, runtime dependencies, test/lint configuration.
- `backend/__init__.py` — package marker.
- `backend/app/__init__.py` — application package marker.
- `backend/app/main.py` — `create_app()` and router/exception registration.
- `backend/app/config.py` — frozen environment-backed settings and constants.
- `backend/app/exceptions.py` — HTTP-agnostic domain exceptions.
- `backend/app/api/__init__.py` — API package marker.
- `backend/app/api/schemas/__init__.py` — schema package marker.
- `backend/app/api/schemas/file_embeddings.py` — upload response and error DTOs.
- `backend/app/api/schemas/health.py` — health response DTO.
- `backend/app/api/routes/__init__.py` — route package marker.
- `backend/app/api/routes/file_embeddings.py` — thin upload route.
- `backend/app/api/routes/health.py` — health route.
- `backend/app/file_processing/__init__.py` — processing package marker.
- `backend/app/file_processing/types.py` — immutable typed processing values.
- `backend/app/file_processing/detect.py` — content-based MIME classification.
- `backend/app/file_processing/extract.py` — text, image, and PDF conversion.
- `backend/app/file_processing/service.py` — file-size checks and group-specific processing.
- `backend/app/integrations/__init__.py` — integration package marker.
- `backend/app/integrations/model_client.py` — model adapter protocol and OpenAI-compatible implementation.
- `backend/app/integrations/qdrant_store.py` — Qdrant adapter protocol and collection/upsert/health operations.
- `backend/app/file_embeddings/__init__.py` — feature package marker.
- `backend/app/file_embeddings/service.py` — request validation, per-file orchestration, and result creation.
- `backend/tests/conftest.py` — app/settings/client fixtures.
- `backend/tests/unit/test_schemas.py` — DTO validation tests.
- `backend/tests/unit/test_detect.py` — MIME classification tests.
- `backend/tests/unit/test_extract.py` — text/image/PDF extraction tests.
- `backend/tests/unit/test_file_processing.py` — size and empty-file tests.
- `backend/tests/unit/test_model_client.py` — model adapter tests with mocked SDK.
- `backend/tests/unit/test_qdrant_store.py` — Qdrant adapter tests with mocked client.
- `backend/tests/unit/test_embeddings_service.py` — per-file success/error orchestration tests.
- `backend/tests/integration/test_routes.py` — upload and health endpoint tests with dependency overrides.
- `Dockerfile` — minimal production image with libmagic runtime support, Python dependencies, and Uvicorn entrypoint.
- `docker-compose.yml` — local app plus Qdrant orchestration, persistent Qdrant volume, health check, and environment wiring.
- `.dockerignore` — excludes virtual environments, caches, git metadata, secrets, and local Qdrant data from image build context.

### Modify

- `.env.example` — add Compose-specific `APP_PORT`, `QDRANT_PORT`, and model endpoint guidance.
- `README.md` — add Compose startup, health, and request commands.

### Preserve

- `embed.py` — existing standalone helper remains untouched unless implementation discovers a required compatibility wrapper. New service imports its own typed model adapter rather than coupling routes to this file.
- `docs/superpowers/specs/2026-07-10-openai-file-embeddings-design.md` — source specification.

---

## Task 1: Bootstrap Python Service and Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/conftest.py`

**Interfaces:**
- Produces `backend.app.main:create_app` import target for later tasks.
- Produces pytest configuration with `unit` and `integration` markers.

- [ ] **Step 1: Write the failing import test**

Create `backend/tests/conftest.py` with a smoke test fixture only after adding this test to `backend/tests/unit/test_bootstrap.py`:

```python
from backend.app.main import create_app


def test_create_app_returns_fastapi_application():
    app = create_app()
    assert app.title == "OpenAI File Embeddings"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest backend/tests/unit/test_bootstrap.py::test_create_app_returns_fastapi_application -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.main'`.

- [ ] **Step 3: Add package metadata and minimal app**

Add runtime dependencies for FastAPI, Uvicorn, Pydantic Settings, python-magic, Pillow, pypdf, OpenAI, and Qdrant. Add pytest, pytest-cov, and httpx as development dependencies. Configure Ruff and pytest markers.

Create the minimum `backend/app/main.py`:

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="OpenAI File Embeddings")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest backend/tests/unit/test_bootstrap.py::test_create_app_returns_fastapi_application -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
dont commit anything
```

---

## Task 2: Add Configuration, DTOs, and Domain Errors

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/exceptions.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/schemas/__init__.py`
- Create: `backend/app/api/schemas/file_embeddings.py`
- Create: `backend/app/api/schemas/health.py`
- Create: `backend/tests/unit/test_schemas.py`

**Interfaces:**
- Produces frozen `Settings` with `MODEL_ENDPOINT_URL`, optional `MODEL_ENDPOINT_API_KEY`, `MODEL_REQUEST_TIMEOUT`, `QDRANT_URL`, optional `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `QDRANT_VECTOR_SIZE`, and `QDRANT_DISTANCE`.
- Produces `FileEmbeddingItem`, `FileEmbeddingResponse`, `ErrorDetail`, `ErrorResponse`, and `HealthResponse`.
- Produces `SettingsError`, `FileProcessingError`, `ModelEndpointError`, and `QdrantStorageError`.

- [ ] **Step 1: Write failing validation tests**

```python
import pytest
from pydantic import ValidationError

from backend.app.api.schemas.file_embeddings import (
    ErrorDetail,
    FileEmbeddingItem,
    FileEmbeddingResponse,
)
from backend.app.api.schemas.health import HealthResponse


def test_success_item_has_empty_error():
    item = FileEmbeddingItem(
        filename="report.txt",
        content_type="text/plain",
        error="",
    )
    assert item.filename == "report.txt"
    assert item.error == ""


def test_error_item_preserves_safe_message():
    item = FileEmbeddingItem(
        filename="bad.bin",
        content_type="application/octet-stream",
        error="Unsupported file type",
    )
    assert item.error == "Unsupported file type"


def test_response_uses_list_object_marker():
    response = FileEmbeddingResponse(
        object="list",
        data=[FileEmbeddingItem(filename="x.txt", content_type="text/plain")],
    )
    assert response.object == "list"
    assert len(response.data) == 1


def test_error_detail_requires_message_and_type():
    with pytest.raises(ValidationError):
        ErrorDetail(message="only message")


def test_health_response_contains_dependency_statuses():
    response = HealthResponse(status="ok", qdrant="ok", model="ok")
    assert response.model == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_schemas.py -q
```

Expected: FAIL because schema modules do not exist.

- [ ] **Step 3: Implement typed immutable schemas and settings**

Use Pydantic `ConfigDict(frozen=True)` for DTOs. Define `FileEmbeddingItem` defaults as `content_type: str = ""` and `error: str = ""`; define `FileEmbeddingResponse(object: Literal["list"] = "list", data: list[FileEmbeddingItem])`; define `ErrorDetail(message: str, type: str, filename: str = "")`; define `ErrorResponse(error: ErrorDetail)`; define `HealthResponse(status: str, qdrant: str, model: str)`.

Use `BaseSettings` with environment aliases matching the spec and defaults: request timeout 30 seconds, collection `file_embeddings`, vector size required, distance `Cosine`. Reject non-positive timeout/vector size with `Field(gt=0)`. Domain exceptions contain safe public messages and optional internal causes without importing FastAPI.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest backend/tests/unit/test_schemas.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/exceptions.py backend/app/api backend/tests/unit/test_schemas.py
 git commit -m "feat: add service settings and response schemas"
```

---

## Task 3: Implement Content-Based File Detection and Extraction

**Files:**
- Create: `backend/app/file_processing/__init__.py`
- Create: `backend/app/file_processing/types.py`
- Create: `backend/app/file_processing/detect.py`
- Create: `backend/app/file_processing/extract.py`
- Create: `backend/app/file_processing/service.py`
- Create: `backend/tests/unit/test_detect.py`
- Create: `backend/tests/unit/test_extract.py`
- Create: `backend/tests/unit/test_file_processing.py`

**Interfaces:**
- Produces `FileGroup = Literal["text", "image", "pdf"]`.
- Produces immutable `ProcessedInput(kind: Literal["text", "image"], value: str | bytes)`.
- Produces `detect_file_group(content: bytes) -> FileGroup` and raises `FileProcessingError` for unsupported MIME.
- Produces `extract_text(content: bytes) -> str`, `validate_image(content: bytes) -> None`, and `extract_pdf_text(content: bytes) -> str`.
- Produces `process_file(content: bytes, filename: str, content_type: str) -> ProcessedInput`.

- [ ] **Step 1: Write failing MIME and extraction tests**

```python
from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfWriter

from backend.app.exceptions import FileProcessingError
from backend.app.file_processing.detect import detect_file_group
from backend.app.file_processing.extract import (
    extract_pdf_text,
    extract_text,
    validate_image,
)


def test_detects_plain_text_from_content():
    assert detect_file_group(b"hello") == "text"


def test_detects_png_from_content():
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    assert detect_file_group(output.getvalue()) == "image"


def test_detects_pdf_from_content():
    output = BytesIO()
    PdfWriter().write(output)
    assert detect_file_group(output.getvalue()) == "pdf"


def test_rejects_unknown_content():
    with pytest.raises(FileProcessingError, match="Unsupported file type"):
        detect_file_group(b"not a known format")


def test_decodes_utf8_text():
    assert extract_text("café".encode()) == "café"


def test_rejects_invalid_utf8():
    with pytest.raises(FileProcessingError, match="decode"):
        extract_text(b"\xff\xfe")


def test_validates_image_bytes():
    output = BytesIO()
    Image.new("RGB", (1, 1), "blue").save(output, format="PNG")
    validate_image(output.getvalue())


def test_rejects_invalid_image_bytes():
    with pytest.raises(FileProcessingError, match="image"):
        validate_image(b"not image bytes")
```

Add PDF text extraction fixture using a generated text PDF or a small checked-in fixture. Assert text extraction returns non-empty text and a blank PDF raises `FileProcessingError("PDF has no extractable text")`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_detect.py backend/tests/unit/test_extract.py -q
```

Expected: FAIL because processing modules do not exist.

- [ ] **Step 3: Implement detection and extraction**

Read bytes once. Call `magic.from_buffer(content, mime=True)`. Map `text/plain`, `text/csv`, `text/markdown`, `application/json`, `application/xml`, `text/yaml`, `text/x-yaml`, `text/html`, `text/css`, and `text/x-*` to text; map PNG/JPEG/WEBP MIME values to image; map `application/pdf` to PDF; raise a safe unsupported-type error otherwise.

Decode text strictly as UTF-8. Open image bytes with Pillow, call `verify()`, and convert library exceptions into `FileProcessingError("Invalid image")`. Extract all PDF pages with pypdf, join page text, strip whitespace, and raise `FileProcessingError("PDF has no extractable text")` when empty.

`process_file` must reject zero bytes before detection, enforce `len(content) <= 25 * 1024 * 1024`, then return `ProcessedInput(kind="text", value=...)` for text/PDF or `ProcessedInput(kind="image", value=content)` for images. Never write uploaded bytes to disk or use the original filename as a path.

- [ ] **Step 4: Add boundary tests**

```python
from backend.app.exceptions import FileProcessingError
from backend.app.file_processing.service import process_file


def test_rejects_empty_file():
    with pytest.raises(FileProcessingError, match="Empty file"):
        process_file(b"", "empty.txt", "text/plain")


def test_rejects_file_over_25_mb():
    content = b"x" * (25 * 1024 * 1024 + 1)
    with pytest.raises(FileProcessingError, match="25 MB"):
        process_file(content, "large.txt", "text/plain")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest backend/tests/unit/test_detect.py backend/tests/unit/test_extract.py backend/tests/unit/test_file_processing.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/file_processing backend/tests/unit/test_detect.py backend/tests/unit/test_extract.py backend/tests/unit/test_file_processing.py
git commit -m "feat: add safe text image and PDF processing"
```

---

## Task 4: Add External Model Adapter

**Files:**
- Create: `backend/app/integrations/__init__.py`
- Create: `backend/app/integrations/model_client.py`
- Create: `backend/tests/unit/test_model_client.py`

**Interfaces:**
- Produces `ModelClient` protocol with `embed_text(text: str, model: str) -> list[float]`, `embed_image(image_bytes: bytes, model: str) -> list[float]`, and `check_health() -> str`.
- Produces `OpenAICompatibleModelClient(settings: Settings)` implementing the protocol.
- Produces safe mapping of timeout/rejection/transport failures to `ModelEndpointError`.

- [ ] **Step 1: Write failing adapter tests**

```python
from unittest.mock import Mock

import pytest

from backend.app.exceptions import ModelEndpointError
from backend.app.integrations.model_client import OpenAICompatibleModelClient


def test_embed_text_returns_embedding_from_sdk_response():
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[0.1, 0.2])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    assert client.embed_text("hello", "model-a") == [0.1, 0.2]
    sdk.embeddings.create.assert_called_once_with(model="model-a", input="hello")


def test_embed_image_sends_base64_data_url():
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[0.3])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    result = client.embed_image(b"png-bytes", "vision-model")

    assert result == [0.3]
    call = sdk.embeddings.create.call_args.kwargs
    assert call["model"] == "vision-model"
    assert call["input"].startswith("data:image/png;base64,")


def test_model_timeout_becomes_safe_domain_error():
    sdk = Mock()
    sdk.embeddings.create.side_effect = TimeoutError()
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError, match="timed out"):
        client.embed_text("hello", "model-a")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_model_client.py -q
```

Expected: FAIL because adapter module does not exist.

- [ ] **Step 3: Implement adapter**

Construct `OpenAI(base_url=settings.model_endpoint_url, api_key=settings.model_endpoint_api_key or "not-needed", timeout=settings.model_request_timeout)`. Keep SDK creation in the adapter, never in routes. Call `embeddings.create` with text directly. Encode image bytes with standard-library base64 and send a `data:image/png;base64,...` input string, matching the model endpoint contract in the specification. Validate response contains exactly one item with a non-empty numeric embedding; otherwise raise `ModelEndpointError("Model endpoint returned an invalid embedding")`.

Catch SDK timeout, connection, and API exceptions; log exception details server-side without API keys; expose only `Model endpoint timed out` or `Model endpoint rejected input` to per-file results. `check_health()` returns `"ok"` on a successful minimal model request or `"unavailable"` on failure without raising.

Provide `from_client()` test constructor so unit tests inject a mock SDK without changing production configuration.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest backend/tests/unit/test_model_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/__init__.py backend/app/integrations/model_client.py backend/tests/unit/test_model_client.py
git commit -m "feat: add OpenAI-compatible model adapter"
```

---

## Task 5: Add Qdrant Storage Adapter

**Files:**
- Create: `backend/app/integrations/qdrant_store.py`
- Create: `backend/tests/unit/test_qdrant_store.py`

**Interfaces:**
- Produces `QdrantStore` protocol with `ensure_collection() -> None`, `store_embedding(embedding: list[float]) -> str`, and `check_health() -> str`.
- Produces `QdrantEmbeddingStore(settings: Settings)` implementation.
- `store_embedding` returns generated UUID string after upsert.

- [ ] **Step 1: Write failing storage tests**

```python
from unittest.mock import Mock

from backend.app.integrations.qdrant_store import QdrantEmbeddingStore


def test_ensure_collection_creates_missing_collection():
    client = Mock()
    client.collection_exists.return_value = False
    store = QdrantEmbeddingStore.from_client(client, vector_size=2, collection="file_embeddings")

    store.ensure_collection()

    client.create_collection.assert_called_once()


def test_store_embedding_upserts_uuid_point_without_payload():
    client = Mock()
    store = QdrantEmbeddingStore.from_client(client, vector_size=2, collection="file_embeddings")

    point_id = store.store_embedding([0.1, 0.2])

    assert point_id
    request = client.upsert.call_args.kwargs
    point = request["points"][0]
    assert point.vector == [0.1, 0.2]
    assert point.payload is None


def test_health_returns_unavailable_on_client_failure():
    client = Mock()
    client.get_collections.side_effect = RuntimeError("down")
    store = QdrantEmbeddingStore.from_client(client, vector_size=2, collection="file_embeddings")

    assert store.check_health() == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_qdrant_store.py -q
```

Expected: FAIL because storage adapter does not exist.

- [ ] **Step 3: Implement collection and upsert behavior**

Construct `QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)` once in the adapter. `ensure_collection` calls `collection_exists`; when false, creates `VectorParams(size=settings.qdrant_vector_size, distance=Distance.COSINE)` and uses the configured collection name. `store_embedding` creates `PointStruct(id=str(uuid4()), vector=embedding, payload=None)` and calls `upsert(wait=True)`. Convert client failures into `QdrantStorageError("Qdrant storage failure")`.

`check_health` calls `get_collections` and returns `"ok"` or `"unavailable"`. Add `from_client()` constructor for mock tests.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest backend/tests/unit/test_qdrant_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/qdrant_store.py backend/tests/unit/test_qdrant_store.py
git commit -m "feat: add Qdrant embedding storage"
```

---

## Task 6: Implement Per-File Embedding Orchestration

**Files:**
- Create: `backend/app/file_embeddings/__init__.py`
- Create: `backend/app/file_embeddings/service.py`
- Create: `backend/tests/unit/test_embeddings_service.py`

**Interfaces:**
- Produces immutable `FileUpload` value with `filename: str`, `content_type: str`, and `content: bytes`.
- Produces `FileEmbeddingService(model_client: ModelClient, qdrant_store: QdrantStore)`.
- Produces `process_files(files: Sequence[FileUpload], model: str) -> FileEmbeddingResponse`.
- Produces `startup() -> None` that ensures Qdrant collection exists before requests.

- [ ] **Step 1: Write failing orchestration tests**

```python
from unittest.mock import Mock

from backend.app.file_embeddings.service import FileEmbeddingService, FileUpload


def test_processes_text_file_and_stores_vector():
    model = Mock()
    model.embed_text.return_value = [0.1, 0.2]
    qdrant = Mock()
    qdrant.store_embedding.return_value = "point-1"
    service = FileEmbeddingService(model, qdrant)

    response = service.process_files(
        [FileUpload("note.txt", "text/plain", b"hello")],
        "model-a",
    )

    assert response.data[0].filename == "note.txt"
    assert response.data[0].error == ""
    model.embed_text.assert_called_once_with("hello", "model-a")
    qdrant.store_embedding.assert_called_once_with([0.1, 0.2])


def test_one_bad_file_does_not_stop_next_file():
    model = Mock()
    model.embed_text.side_effect = [RuntimeError("rejected"), [0.4]]
    qdrant = Mock()
    service = FileEmbeddingService(model, qdrant)

    response = service.process_files(
        [
            FileUpload("bad.txt", "text/plain", b"bad"),
            FileUpload("good.txt", "text/plain", b"good"),
        ],
        "model-a",
    )

    assert response.data[0].error == "Model endpoint rejected input"
    assert response.data[1].error == ""
    assert len(response.data) == 2


def test_startup_ensures_collection():
    qdrant = Mock()
    service = FileEmbeddingService(Mock(), qdrant)

    service.startup()

    qdrant.ensure_collection.assert_called_once_with()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/unit/test_embeddings_service.py -q
```

Expected: FAIL because orchestration module does not exist.

- [ ] **Step 3: Implement orchestration**

For each upload, call `process_file`. Route `ProcessedInput.kind == "text"` to `model_client.embed_text(str(value), model)` and `kind == "image"` to `embed_image(bytes(value), model)`. On success, call `qdrant_store.store_embedding(vector)` and return a `FileEmbeddingItem` with original filename/content type and empty error. Catch `FileProcessingError`, `ModelEndpointError`, and `QdrantStorageError` and place their safe messages in that file's item. Catch unexpected exceptions, log filename and exception type without content/secrets, and return `Processing failed`.

Do not return point IDs or vectors. Preserve input order. `startup()` calls `ensure_collection()` once during app startup; if it fails, allow the app startup failure to surface as a service configuration/dependency error.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest backend/tests/unit/test_embeddings_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/file_embeddings backend/tests/unit/test_embeddings_service.py
git commit -m "feat: orchestrate per-file embedding and storage"
```

---

## Task 7: Add FastAPI Upload and Health Routes

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/file_embeddings.py`
- Create: `backend/app/api/routes/health.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_routes.py`

**Interfaces:**
- Registers `POST /v1/file-embeddings` with `response_model=FileEmbeddingResponse` and `status_code=200`.
- Registers `GET /health` with `response_model=HealthResponse` and `status_code=200`.
- Route dependencies provide a configured `FileEmbeddingService` and health dependencies; tests override exact dependencies.

- [ ] **Step 1: Write failing route tests**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import create_app


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_route_returns_one_result_per_file(fake_service):
    app = create_app(service=fake_service)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/file-embeddings",
            data={"model": "model-a"},
            files=[
                ("files", ("one.txt", b"hello", "text/plain")),
                ("files", ("two.txt", b"world", "text/plain")),
            ],
        )

    assert response.status_code == 200
    assert response.json()["object"] == "list"
    assert [item["filename"] for item in response.json()["data"]] == ["one.txt", "two.txt"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_route_rejects_missing_files():
    app = create_app(service=FakeService())
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/file-embeddings", data={"model": "model-a"})

    assert response.status_code == 400
    assert "No files provided" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_upload_route_rejects_more_than_ten_files():
    app = create_app(service=FakeService())
    transport = ASGITransport(app=app)
    files = [("files", (f"{index}.txt", b"x", "text/plain")) for index in range(11)]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/file-embeddings",
            data={"model": "model-a"},
            files=files,
        )

    assert response.status_code == 400
    assert "10" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_health_reports_dependency_statuses(fake_health_dependencies):
    app = create_app(health_dependencies=fake_health_dependencies)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "qdrant": "ok", "model": "ok"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/integration/test_routes.py -q
```

Expected: FAIL because routes and injectable app dependencies do not exist.

- [ ] **Step 3: Implement dependency construction and routes**

Update `create_app()` to accept optional `service` and optional health dependencies for tests. Production construction reads `Settings`, creates `OpenAICompatibleModelClient` and `QdrantEmbeddingStore`, creates `FileEmbeddingService`, and registers a startup handler that calls `service.startup()`.

Use regular synchronous route handlers because all selected libraries and SDK clients are synchronous:

```python
@router.post("/v1/file-embeddings", response_model=FileEmbeddingResponse, status_code=200)
def create_file_embeddings(
    files: list[UploadFile] = File(...),
    model: str = Form(..., min_length=1),
    service: FileEmbeddingService = Depends(get_file_embedding_service),
) -> FileEmbeddingResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided. Please attach at least one file.")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per request.")
    uploads = [FileUpload(file.filename or "", file.content_type or "", file.file.read()) for file in files]
    return service.process_files(uploads, model)
```

Reject blank model values with HTTP 422 through `Form(min_length=1)`. Keep upload route free of detection, parsing, SDK, and Qdrant logic. Register `/health` to call both adapters and return `HealthResponse`; use overall status `ok` only when both dependencies report `ok`, otherwise `degraded`.

Map startup dependency failure to an application startup failure, not a per-file error. Return safe HTTP error details and never log filenames as paths or credentials.

- [ ] **Step 4: Add missing-file, limit, and dependency-failure tests**

Assert empty upload bytes produce normal 200 response with per-file `Empty file` error. Assert a 25 MB + 1 byte upload produces per-file error while another valid file succeeds. Assert model timeout and Qdrant failure remain per-file errors. Assert health returns `degraded` when either dependency is unavailable.

- [ ] **Step 5: Run route tests to verify they pass**

Run:

```bash
pytest backend/tests/integration/test_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/routes backend/tests/conftest.py backend/tests/integration/test_routes.py
git commit -m "feat: expose file embeddings and health endpoints"
```

---

## Task 8: Add Full Error Coverage, Configuration Checks, and Documentation

**Files:**
- Modify: `backend/tests/unit/test_model_client.py`
- Modify: `backend/tests/unit/test_qdrant_store.py`
- Modify: `backend/tests/unit/test_embeddings_service.py`
- Modify: `backend/tests/integration/test_routes.py`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Documents exact environment names and launch command.
- Confirms all request-level and per-file error behaviors from the source spec.

- [ ] **Step 1: Write failing configuration and error tests**

Add these tests:

```python
def test_settings_requires_model_and_qdrant_urls(monkeypatch):
    monkeypatch.delenv("MODEL_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(QDRANT_VECTOR_SIZE=2)


def test_all_file_failures_still_return_normal_response():
    response = service.process_files(
        [FileUpload("bad.bin", "application/octet-stream", b"bad")],
        "model-a",
    )
    assert response.data[0].error == "Unsupported file type"
```

Add one endpoint test per remaining behavior: blank model returns HTTP 422; an oversized upload returns a per-file 25 MB error; model timeout returns a per-file timeout error; model rejection returns a per-file rejection error; Qdrant upsert failure returns a per-file storage error; unavailable Qdrant or model health returns overall `degraded`. Assert serialized responses contain no vector values, point IDs, API keys, exception tracebacks, or local paths.

- [ ] **Step 2: Run tests to verify missing cases fail**

Run:

```bash
pytest backend/tests -q
```

Expected: newly added assertions fail until exact mappings/config checks are complete.

- [ ] **Step 3: Implement exact error mappings and docs**

Ensure request-level errors use HTTP 400 for no files and more than 10 files; FastAPI validation returns 422 for missing/blank model; per-file errors stay inside `FileEmbeddingResponse` with HTTP 200 even when every file fails. Ensure model timeout maps to `Model endpoint timed out`, model rejection maps to `Model endpoint rejected input`, Qdrant failures map to `Qdrant storage failure`, and PDF/image/text errors use the exact safe messages from the spec.

Create `.env.example`:

```dotenv
MODEL_ENDPOINT_URL=http://localhost:8000/v1
MODEL_ENDPOINT_API_KEY=
MODEL_REQUEST_TIMEOUT=30
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=file_embeddings
QDRANT_VECTOR_SIZE=1536
QDRANT_DISTANCE=Cosine
```

Create `README.md` covering installation, `uv run uvicorn backend.app.main:create_app --factory --reload`, multipart request example, response shape, supported MIME groups, 10-file/25 MB limits, required Qdrant collection setup, no-OCR PDF behavior, and no-auth trusted-network limitation.

- [ ] **Step 4: Run complete test suite and coverage**

Run:

```bash
pytest backend/tests --cov=backend/app --cov-report=term-missing -q
```

Expected: all tests pass and coverage is at least 80%. If coverage is below 80%, add tests for uncovered branches in adapters, health degradation, and per-file exception mapping; do not weaken coverage threshold.

- [ ] **Step 5: Run formatting and lint checks**

Run:

```bash
uv run ruff format --check backend
uv run ruff check backend
```

Expected: both commands pass with no import, annotation, or style errors.

- [ ] **Step 6: Run app import check**

Run:

```bash
MODEL_ENDPOINT_URL=http://localhost:8000/v1 QDRANT_URL=http://localhost:6333 QDRANT_VECTOR_SIZE=1536 python -c 'from backend.app.main import create_app; print(create_app().title)'
```

Expected: `OpenAI File Embeddings`.

- [ ] **Step 7: Commit**

```bash
git add backend/tests .env.example README.md
 git commit -m "test: cover file embedding errors and document service"
```

---

## Task 9: Add Docker Compose Deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Produces app image exposing port 8000 and running `backend.app.main:create_app` through Uvicorn.
- Produces Qdrant service reachable from app as `http://qdrant:6333`.
- Produces persistent Docker volume `qdrant_storage` mounted at `/qdrant/storage`.
- Requires model endpoint URL, model API key when needed, and vector size through environment variables; Compose does not hardcode secrets or assume model container ownership.

- [ ] **Step 1: Write failing Compose validation checks**

Create `backend/tests/integration/test_compose_files.py`:

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[3]


def test_compose_defines_app_and_qdrant_services():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())

    assert set(compose["services"]) == {"app", "qdrant"}
    assert compose["services"]["app"]["build"] == "."
    assert compose["services"]["app"]["environment"]["QDRANT_URL"] == "http://qdrant:6333"
    assert compose["services"]["qdrant"]["volumes"] == ["qdrant_storage:/qdrant/storage"]


def test_dockerfile_installs_libmagic_and_runs_uvicorn():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "libmagic1" in dockerfile
    assert "uvicorn" in dockerfile
    assert "backend.app.main:create_app" in dockerfile
```

Add `PyYAML` to test dependencies only if not already available; use `docker compose config` as the authoritative parser check.

- [ ] **Step 2: Run checks to verify they fail**

Run:

```bash
pytest backend/tests/integration/test_compose_files.py -q
docker compose config
```

Expected: pytest fails because Compose files do not exist; Docker Compose reports missing configuration.

- [ ] **Step 3: Create minimal Docker image**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Keep image free of `.env`, virtual environments, git metadata, test caches, and local Qdrant data through `.dockerignore`.

- [ ] **Step 4: Create Compose services and health checks**

Create `docker-compose.yml`:

```yaml
services:
  app:
    build: .
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      MODEL_ENDPOINT_URL: "${MODEL_ENDPOINT_URL:?Set MODEL_ENDPOINT_URL in .env}"
      MODEL_ENDPOINT_API_KEY: "${MODEL_ENDPOINT_API_KEY:-}"
      MODEL_REQUEST_TIMEOUT: "${MODEL_REQUEST_TIMEOUT:-30}"
      QDRANT_URL: "http://qdrant:6333"
      QDRANT_API_KEY: "${QDRANT_API_KEY:-}"
      QDRANT_COLLECTION: "${QDRANT_COLLECTION:-file_embeddings}"
      QDRANT_VECTOR_SIZE: "${QDRANT_VECTOR_SIZE:?Set QDRANT_VECTOR_SIZE in .env}"
      QDRANT_DISTANCE: "${QDRANT_DISTANCE:-Cosine}"
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "${QDRANT_PORT:-6333}:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test:
        - CMD
        - bash
        - -c
        - "bash -euo pipefail -c 'cat < /dev/null > /dev/tcp/localhost/6333'"
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  qdrant_storage:
```

Compose must use service DNS `http://qdrant:6333` inside app, not host `localhost`. `MODEL_ENDPOINT_URL` remains external/configurable. Do not add model credentials directly to YAML.

- [ ] **Step 5: Document Compose usage**

Extend `.env.example`:

```dotenv
APP_PORT=8000
QDRANT_PORT=6333
MODEL_ENDPOINT_URL=http://host.docker.internal:8001/v1
MODEL_ENDPOINT_API_KEY=
MODEL_REQUEST_TIMEOUT=30
QDRANT_API_KEY=
QDRANT_COLLECTION=file_embeddings
QDRANT_VECTOR_SIZE=1536
QDRANT_DISTANCE=Cosine
```

Document commands in `README.md`:

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/file-embeddings \\
  -F model=text-embedding-3-small \\
  -F files=@README.md
```

Explain that `host.docker.internal` reaches a model running on the host from Docker Desktop; replace it with a reachable model URL in other environments. Explain `docker compose down` keeps named volume data and `docker compose down -v` deletes local Qdrant data.

- [ ] **Step 6: Run checks to verify they pass**

Run:

```bash
docker compose config
pytest backend/tests/integration/test_compose_files.py -q
docker compose build app
docker compose up -d qdrant
docker compose ps
curl --fail http://localhost:${QDRANT_PORT:-6333}/healthz
docker compose down
```

Expected: Compose config parses; validation tests pass; app image builds; Qdrant reaches healthy state; cleanup stops services without deleting `qdrant_storage`.

- [ ] **Step 7: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore .env.example README.md backend/tests/integration/test_compose_files.py
 git commit -m "chore: add Docker Compose deployment"
```

---

## Final Verification Checklist

- [ ] `POST /v1/file-embeddings` accepts multipart uploads and model field.
- [ ] Missing files and more than 10 files return request-level client errors.
- [ ] Files over 25 MB and empty files receive safe per-file errors.
- [ ] MIME detection uses content bytes, not filename extension.
- [ ] UTF-8 text, valid PNG/JPEG/WEBP, and text PDFs succeed.
- [ ] Invalid UTF-8, invalid images, blank PDFs, and unsupported MIME types fail per file.
- [ ] Model adapter handles text and image inputs and maps timeout/rejection failures.
- [ ] Qdrant collection is ensured at startup and each successful file creates one UUID point with no payload.
- [ ] Response includes filename, content type, and error only; no vectors or point IDs.
- [ ] `/health` reports process, Qdrant, and model status with `ok`/`degraded` overall status.
- [ ] No secrets are hardcoded or logged.
- [ ] Dockerfile builds successfully with libmagic runtime support.
- [ ] `docker compose config` passes with required model URL and vector size supplied through `.env`.
- [ ] Compose app reaches healthy state after Qdrant becomes healthy.
- [ ] Qdrant data persists in named volume across app restarts.
- [ ] Unit and integration tests pass with at least 80% coverage.
- [ ] Ruff format and lint pass.
