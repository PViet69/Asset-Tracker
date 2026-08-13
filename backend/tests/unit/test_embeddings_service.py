"""Unit tests for per-file embedding orchestration."""

from io import BytesIO
from logging import ERROR
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from backend.app.api.schemas.file_embeddings import FileEmbeddingResponse
from backend.app.exceptions import (
    FileProcessingError,
    ModelEndpointError,
    QdrantStorageError,
)
from backend.app.file_embeddings.service import FileEmbeddingService, FileUpload
from backend.app.file_processing.types import ProcessedInput


def make_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.unit
def test_file_upload_is_immutable() -> None:
    upload = FileUpload("note.txt", "text/plain", b"hello")

    with pytest.raises((AttributeError, TypeError)):
        upload.filename = "changed.txt"

    assert upload.filename == "note.txt"
    assert upload.content_type == "text/plain"
    assert upload.content == b"hello"


@pytest.mark.unit
def test_processes_text_via_file_processor_and_hides_storage_details() -> None:
    model = Mock()
    model.embed_text.return_value = [0.1, 0.2]
    qdrant = Mock()
    qdrant.store_embedding.return_value = "point-secret"
    service = FileEmbeddingService(model, qdrant)
    upload = FileUpload("note.txt", "text/plain", b"source-bytes")

    with patch(
        "backend.app.file_embeddings.service.process_file",
        return_value=ProcessedInput("text", "hello"),
    ) as process_file:
        response = service.process_files([upload], "model-a")

    process_file.assert_called_once_with(b"source-bytes", "note.txt", "text/plain")
    model.embed_text.assert_called_once_with("hello", "model-a")
    qdrant.store_embedding.assert_called_once_with([0.1, 0.2])
    item = response.data[0]
    assert item.filename == "note.txt"
    assert item.status == "success"
    assert item.reason is None
    assert set(item.model_dump()) == {"filename", "content_type", "status", "reason"}
    assert "point-secret" not in str(item.model_dump())
    assert "0.1" not in str(item.model_dump())


@pytest.mark.unit
def test_real_processing_returns_normal_response_when_all_files_fail() -> None:
    model = Mock()
    qdrant = Mock()
    service = FileEmbeddingService(model, qdrant)

    response = service.process_files(
        [FileUpload("bad.bin", "application/octet-stream", b"\x1f\x8b\x08\x00")],
        "model-a",
    )

    assert isinstance(response, FileEmbeddingResponse)
    assert response.model_dump() == {
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
    model.embed_text.assert_not_called()
    model.embed_image.assert_not_called()
    qdrant.store_embedding.assert_not_called()


@pytest.mark.unit
def test_valid_png_routes_to_image_embedding() -> None:
    model = Mock()
    model.embed_image.return_value = [0.3]
    qdrant = Mock()
    service = FileEmbeddingService(model, qdrant)
    png = make_png()

    response = service.process_files(
        [FileUpload("photo.png", "image/png", png)],
        "vision-model",
    )

    model.embed_image.assert_called_once_with(png, "vision-model")
    model.embed_text.assert_not_called()
    qdrant.store_embedding.assert_called_once_with([0.3])
    assert response.data[0].filename == "photo.png"
    assert response.data[0].status == "success"
    assert response.data[0].reason is None


@pytest.mark.unit
def test_model_error_preserves_safe_message_and_continues_in_order() -> None:
    model = Mock()
    model.embed_text.side_effect = [
        ModelEndpointError("Model endpoint rejected input"),
        [0.4],
    ]
    qdrant = Mock()
    service = FileEmbeddingService(model, qdrant)
    uploads = [
        FileUpload("bad.txt", "text/plain", b"bad"),
        FileUpload("good.txt", "text/plain", b"good"),
    ]

    with patch(
        "backend.app.file_embeddings.service.process_file",
        side_effect=[ProcessedInput("text", "bad"), ProcessedInput("text", "good")],
    ):
        response = service.process_files(uploads, "model-a")

    assert [item.filename for item in response.data] == ["bad.txt", "good.txt"]
    assert [(item.status, item.reason) for item in response.data] == [
        ("failed", "Model endpoint rejected input"),
        ("success", None),
    ]
    qdrant.store_embedding.assert_called_once_with([0.4])


@pytest.mark.unit
def test_file_processing_error_returns_safe_message() -> None:
    service = FileEmbeddingService(Mock(), Mock())

    with patch(
        "backend.app.file_embeddings.service.process_file",
        side_effect=FileProcessingError("Unsupported file type"),
    ):
        response = service.process_files(
            [FileUpload("bad.bin", "application/octet-stream", b"bytes")],
            "model-a",
        )

    assert response.data[0].status == "failed"
    assert response.data[0].reason == "Unsupported file type"


@pytest.mark.unit
def test_qdrant_storage_error_returns_safe_message() -> None:
    model = Mock()
    model.embed_text.return_value = [0.1]
    qdrant = Mock()
    qdrant.store_embedding.side_effect = QdrantStorageError("Qdrant storage failure")
    service = FileEmbeddingService(model, qdrant)

    with patch(
        "backend.app.file_embeddings.service.process_file",
        return_value=ProcessedInput("text", "hello"),
    ):
        response = service.process_files(
            [FileUpload("note.txt", "text/plain", b"bytes")],
            "model-a",
        )

    assert response.data[0].status == "failed"
    assert response.data[0].reason == "Qdrant storage failure"


@pytest.mark.unit
def test_unexpected_error_returns_safe_message_and_logs_context_without_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = FileEmbeddingService(Mock(), Mock())
    file_content = b"secret file content"
    filename = "private\nforged.txt"

    caplog.set_level(ERROR)
    with patch(
        "backend.app.file_embeddings.service.process_file",
        side_effect=RuntimeError("unexpected failure"),
    ):
        response = service.process_files(
            [FileUpload(filename, "text/plain", file_content)],
            "model-a",
        )

    assert response.data[0].status == "failed"
    assert response.data[0].reason == "Processing failed"
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert filename not in message
    assert repr(filename) in message
    assert "RuntimeError" in message
    assert "unexpected failure" in message
    assert "secret file content" not in message


@pytest.mark.unit
def test_startup_ensures_collection_once() -> None:
    qdrant = Mock()
    service = FileEmbeddingService(Mock(), qdrant)

    service.startup()

    qdrant.ensure_collection.assert_called_once_with()


@pytest.mark.unit
def test_startup_surfaces_qdrant_storage_error() -> None:
    qdrant = Mock()
    qdrant.ensure_collection.side_effect = QdrantStorageError("Qdrant storage failure")
    service = FileEmbeddingService(Mock(), qdrant)

    with pytest.raises(QdrantStorageError, match="Qdrant storage failure"):
        service.startup()

    qdrant.ensure_collection.assert_called_once_with()
