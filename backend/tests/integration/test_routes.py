from dataclasses import dataclass
from inspect import iscoroutinefunction
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from backend.app.api.routes.file_embeddings import create_file_embeddings
from backend.app.api.routes.health import HealthDependencies
from backend.app.api.schemas.file_embeddings import (
    FileEmbeddingItem,
    FileEmbeddingResponse,
)
from backend.app.exceptions import ModelEndpointError, QdrantStorageError
from backend.app.file_embeddings.service import FileEmbeddingService, FileUpload
from backend.app.file_processing.service import MAX_FILE_SIZE
from backend.app.integrations.model_client import (
    ModelClient,
    OpenAICompatibleModelClient,
)
from backend.app.integrations.qdrant_store import QdrantStore
from backend.app.main import create_app
from backend.app.security import MAX_REQUEST_SIZE


@dataclass(frozen=True)
class _HealthModelClient:
    status: str

    def check_health(self) -> str:
        return self.status


@dataclass(frozen=True)
class _HealthQdrantStore:
    status: str

    def check_health(self) -> str:
        return self.status


class _BoundedReadFile(BytesIO):
    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            raise AssertionError("file read must be bounded")
        return super().read(size)


@pytest.mark.integration
def test_create_file_embeddings_is_sync_function() -> None:
    """Route handler must be synchronous for sync SDK/Qdrant operations."""
    assert iscoroutinefunction(create_file_embeddings) is False


@pytest.mark.integration
def test_uploads_files_in_order_and_returns_public_response() -> None:
    service = Mock(spec=FileEmbeddingService)
    service.process_files.return_value = FileEmbeddingResponse(
        data=[
            FileEmbeddingItem(
                filename="first.txt",
                content_type="text/plain",
                status="success",
                reason=None,
            ),
            FileEmbeddingItem(
                filename="second.txt",
                content_type="text/plain",
                status="success",
                reason=None,
            ),
        ]
    )
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[
                ("files", ("first.txt", b"first content", "text/plain")),
                ("files", ("second.txt", b"second content", "text/plain")),
            ],
        )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "filename": "first.txt",
                "content_type": "text/plain",
                "status": "success",
                "reason": None,
            },
            {
                "filename": "second.txt",
                "content_type": "text/plain",
                "status": "success",
                "reason": None,
            },
        ],
    }
    service.process_files.assert_called_once_with(
        [
            FileUpload("first.txt", "text/plain", b"first content"),
            FileUpload("second.txt", "text/plain", b"second content"),
        ],
        "text-embedding-model",
    )
    assert "point_id" not in response.json()
    assert "vector" not in response.json()


@pytest.mark.integration
@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}],
)
def test_upload_requires_configured_api_key(headers: dict[str, str]) -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service, upload_api_key="secret")

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[("files", ("file.txt", b"content", "text/plain"))],
            headers=headers,
        )

    assert response.status_code == 401
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_upload_with_correct_api_key_reaches_service() -> None:
    service = Mock(spec=FileEmbeddingService)
    service.process_files.return_value = FileEmbeddingResponse(data=[])
    app = create_app(service=service, upload_api_key="secret")

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[("files", ("file.txt", b"content", "text/plain"))],
            headers={"Authorization": "Bearer secret"},
        )

    assert response.status_code == 200
    service.process_files.assert_called_once_with(
        [FileUpload("file.txt", "text/plain", b"content")],
        "text-embedding-model",
    )


@pytest.mark.integration
def test_declared_oversized_content_length_returns_payload_too_large() -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings", headers={"Content-Length": str(MAX_REQUEST_SIZE + 1)}
        )

    assert response.status_code == 413
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_upload_without_files_returns_bad_request() -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
        )

    assert response.status_code == 400
    assert "No files provided" in response.json()["detail"]
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_uploading_more_than_ten_files_returns_bad_request() -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service)
    files = [
        ("files", (f"file-{index}.txt", b"content", "text/plain"))
        for index in range(11)
    ]

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=files,
        )

    assert response.status_code == 400
    assert "10" in response.json()["detail"]
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_route_closes_all_uploads_before_rejecting_more_than_ten() -> None:
    service = Mock(spec=FileEmbeddingService)
    file_handles = [_BoundedReadFile(b"content") for _ in range(11)]
    uploads = [
        UploadFile(file=handle, filename=f"file-{index}.txt")
        for index, handle in enumerate(file_handles)
    ]

    with pytest.raises(HTTPException) as raised:
        create_file_embeddings(
            model="text-embedding-model",
            files=uploads,
            service=service,
        )

    assert raised.value.status_code == 400
    assert all(handle.closed for handle in file_handles)
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_route_bounds_oversized_upload_read_and_returns_file_error() -> None:
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    service = FileEmbeddingService(model_client, qdrant_store)
    file_handle = _BoundedReadFile(b"x" * (MAX_FILE_SIZE + 1))
    upload = UploadFile(
        file=file_handle,
        filename="oversized.txt",
        headers={"content-type": "text/plain"},
    )

    response = create_file_embeddings(
        model="text-embedding-model",
        files=[upload],
        service=service,
    )

    assert response.data[0].filename == "oversized.txt"
    assert response.data[0].status == "failed"
    assert response.data[0].reason == "File exceeds 25 MB limit"
    assert file_handle.read_sizes == [MAX_FILE_SIZE + 1]
    assert file_handle.closed
    model_client.embed_text.assert_not_called()
    model_client.embed_image.assert_not_called()
    qdrant_store.store_embedding.assert_not_called()


@pytest.mark.integration
@pytest.mark.parametrize("model", [None, "", "   "])
def test_missing_or_blank_model_returns_unprocessable_entity(
    model: str | None,
) -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service)
    files = [("files", ("file.txt", b"content", "text/plain"))]
    data = {} if model is None else {"model": model}

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data=data,
            files=files,
        )

    assert response.status_code == 422
    service.process_files.assert_not_called()


@pytest.mark.integration
def test_real_service_reports_empty_file_without_embedding_or_storage() -> None:
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[("files", ("empty.txt", b"", "text/plain"))],
        )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "filename": "empty.txt",
            "content_type": "text/plain",
            "status": "failed",
            "reason": "Empty file",
        }
    ]
    model_client.embed_text.assert_not_called()
    model_client.embed_image.assert_not_called()
    qdrant_store.store_embedding.assert_not_called()


@pytest.mark.integration
def test_real_service_preserves_order_for_oversized_and_valid_files() -> None:
    model_client = Mock(spec=ModelClient)
    model_client.embed_text.return_value = [0.123456, -0.654321]
    qdrant_store = Mock(spec=QdrantStore)
    qdrant_store.store_embedding.return_value = "point-secret"
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)
    oversized = b"x" * (25 * 1024 * 1024 + 1)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[
                ("files", ("oversized.txt", oversized, "text/plain")),
                ("files", ("valid.txt", b"valid text", "text/plain")),
            ],
        )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "filename": "oversized.txt",
            "content_type": "text/plain",
            "status": "failed",
            "reason": "File exceeds 25 MB limit",
        },
        {
            "filename": "valid.txt",
            "content_type": "text/plain",
            "status": "success",
            "reason": None,
        },
    ]
    serialized = response.text
    for forbidden in (
        "0.123456",
        "-0.654321",
        "point-secret",
        "sk-test-api-key",
        "Traceback (most recent call last)",
        "/Users/narutojaki/private.txt",
    ):
        assert forbidden not in serialized
    model_client.embed_text.assert_called_once_with(
        "valid text", "text-embedding-model"
    )
    qdrant_store.store_embedding.assert_called_once_with([0.123456, -0.654321])


@pytest.mark.integration
@pytest.mark.parametrize(
    "error_message",
    ["Model endpoint timed out", "Model endpoint rejected input"],
)
def test_real_service_returns_safe_model_error_per_file(error_message: str) -> None:
    model_client = Mock(spec=ModelClient)
    model_client.embed_text.side_effect = ModelEndpointError(error_message)
    qdrant_store = Mock(spec=QdrantStore)
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[("files", ("file.txt", b"valid text", "text/plain"))],
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["status"] == "failed"
    assert response.json()["data"][0]["reason"] == error_message
    qdrant_store.store_embedding.assert_not_called()


@pytest.mark.integration
def test_real_service_returns_200_when_all_files_fail_processing() -> None:
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "model-a"},
            files=[
                (
                    "files",
                    (
                        "bad.bin",
                        b"\x1f\x8b\x08\x00",
                        "application/octet-stream",
                    ),
                )
            ],
        )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "filename": "bad.bin",
                "content_type": "application/octet-stream",
                "status": "failed",
                "reason": "Unsupported file type",
            }
        ],
    }
    model_client.embed_text.assert_not_called()
    model_client.embed_image.assert_not_called()
    qdrant_store.store_embedding.assert_not_called()


@pytest.mark.integration
def test_real_service_returns_safe_qdrant_error_per_file() -> None:
    model_client = Mock(spec=ModelClient)
    model_client.embed_text.return_value = [0.1, 0.2]
    qdrant_store = Mock(spec=QdrantStore)
    qdrant_store.store_embedding.side_effect = QdrantStorageError(
        "Qdrant storage failure"
    )
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)

    with TestClient(app) as client:
        response = client.post(
            "/v1/file-embeddings",
            data={"model": "text-embedding-model"},
            files=[("files", ("file.txt", b"valid text", "text/plain"))],
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["status"] == "failed"
    assert response.json()["data"][0]["reason"] == "Qdrant storage failure"
    model_client.embed_text.assert_called_once_with(
        "valid text", "text-embedding-model"
    )
    qdrant_store.store_embedding.assert_called_once_with([0.1, 0.2])


@pytest.mark.integration
def test_health_uses_model_listing_for_openai_compatible_client() -> None:
    service = Mock(spec=FileEmbeddingService)
    sdk = Mock()
    model_client = OpenAICompatibleModelClient.from_client(sdk)
    dependencies = HealthDependencies(
        model_client=model_client,
        qdrant_store=_HealthQdrantStore("ok"),
    )
    app = create_app(service=service, health_dependencies=dependencies)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "qdrant": "ok", "model": "ok"}
    sdk.models.list.assert_called_once_with()


@pytest.mark.integration
def test_health_is_ok_when_both_dependencies_are_available() -> None:
    service = Mock(spec=FileEmbeddingService)
    dependencies = HealthDependencies(
        model_client=_HealthModelClient("ok"),
        qdrant_store=_HealthQdrantStore("ok"),
    )
    app = create_app(service=service, health_dependencies=dependencies)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "qdrant": "ok", "model": "ok"}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("model_status", "qdrant_status"),
    [("unavailable", "ok"), ("ok", "unavailable"), ("unavailable", "unavailable")],
)
def test_health_is_degraded_when_dependency_is_unavailable(
    model_status: str,
    qdrant_status: str,
) -> None:
    service = Mock(spec=FileEmbeddingService)
    dependencies = HealthDependencies(
        model_client=_HealthModelClient(model_status),
        qdrant_store=_HealthQdrantStore(qdrant_status),
    )
    app = create_app(service=service, health_dependencies=dependencies)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["model"] == model_status
    assert response.json()["qdrant"] == qdrant_status


@pytest.mark.integration
def test_injected_service_starts_once_on_testclient_lifespan() -> None:
    service = Mock(spec=FileEmbeddingService)
    app = create_app(service=service)

    with TestClient(app):
        service.startup.assert_called_once_with()


@pytest.mark.integration
def test_qdrant_startup_error_surfaces_on_testclient_entry() -> None:
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    qdrant_store.ensure_collection.side_effect = QdrantStorageError(
        "Qdrant storage failure"
    )
    service = FileEmbeddingService(model_client, qdrant_store)
    app = create_app(service=service)

    with pytest.raises(QdrantStorageError, match="Qdrant storage failure"):
        with TestClient(app):
            pass
