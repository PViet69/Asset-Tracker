from logging import ERROR
from unittest.mock import Mock, patch

import pytest

from backend.app.api.schemas.file_embeddings import FileEmbeddingResponse
from backend.app.exceptions import (
    FileProcessingError,
    ModelEndpointError,
    QdrantStorageError,
)
from backend.app.file_embeddings.ingestion_service import (
    FileIngestionService,
    FileUpload,
)
from backend.app.file_processing.types import ProcessedInput
from backend.app.model.prompt_model import ImageDescription


def make_description() -> ImageDescription:
    return ImageDescription(
        summary="A green-eyed woman outdoors.",
        subjects=("woman",),
        attributes=("green eyes",),
        actions=("looking at camera",),
        setting=("outdoors",),
        colors=("green",),
        style=("portrait photography",),
        visible_text=(),
        search_keywords=("green-eyed woman", "outdoor portrait"),
    )


def make_service() -> tuple[FileIngestionService, Mock, Mock, Mock]:
    description_client = Mock()
    model_client = Mock()
    model_client.model_name = "embedding-model"
    qdrant_store = Mock()
    service = FileIngestionService(
        description_client,
        model_client,
        qdrant_store,
    )
    return service, description_client, model_client, qdrant_store


@pytest.mark.unit
def test_file_upload_is_immutable() -> None:
    upload = FileUpload("note.txt", "text/plain", b"hello")

    with pytest.raises((AttributeError, TypeError)):
        upload.filename = "changed.txt"

    assert upload.filename == "note.txt"
    assert upload.content_type == "text/plain"
    assert upload.content == b"hello"


@pytest.mark.unit
def test_image_description_text_is_embedded_and_only_vector_is_stored() -> None:
    service, description_client, model_client, qdrant_store = make_service()
    description = make_description()
    description_client.describe.return_value = description
    model_client.embed_text.return_value = [0.3]
    image_bytes = b"validated-image-bytes"
    upload = FileUpload("photo.png", "image/png", image_bytes)

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        return_value=ProcessedInput("image", image_bytes),
    ):
        response = service.process_files((upload,))

    description_client.describe.assert_called_once_with(image_bytes)
    model_client.embed_text.assert_called_once_with(description.to_embedding_text())
    qdrant_store.store_embedding.assert_called_once_with([0.3])
    assert response.data[0].model_dump() == {
        "filename": "photo.png",
        "content_type": "image/png",
        "status": "success",
        "reason": None,
    }
    assert description.summary not in str(response.model_dump())


@pytest.mark.unit
def test_text_bypasses_description_and_embeds_extracted_text() -> None:
    service, description_client, model_client, qdrant_store = make_service()
    model_client.embed_text.return_value = [0.1, 0.2]
    upload = FileUpload("note.txt", "text/plain", b"source-bytes")

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        return_value=ProcessedInput("text", "hello"),
    ) as process_file:
        response = service.process_files((upload,))

    process_file.assert_called_once_with(b"source-bytes", "note.txt", "text/plain")
    description_client.describe.assert_not_called()
    model_client.embed_text.assert_called_once_with("hello")
    qdrant_store.store_embedding.assert_called_once_with([0.1, 0.2])
    assert response.data[0].status == "success"


@pytest.mark.unit
def test_embed_text_uses_configured_embedding_client_without_storage() -> None:
    service, description_client, model_client, qdrant_store = make_service()
    model_client.embed_text.return_value = [0.7]

    assert service.embed_text("query") == [0.7]
    assert service.embedding_model == "embedding-model"
    model_client.embed_text.assert_called_once_with("query")
    description_client.describe.assert_not_called()
    qdrant_store.store_embedding.assert_not_called()


@pytest.mark.unit
def test_description_error_is_safe_and_later_files_continue_in_order() -> None:
    service, description_client, model_client, qdrant_store = make_service()
    description_client.describe.side_effect = ModelEndpointError(
        "Model endpoint failed to describe image"
    )
    model_client.embed_text.return_value = [0.4]
    uploads = (
        FileUpload("bad.png", "image/png", b"image"),
        FileUpload("good.txt", "text/plain", b"text"),
    )

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        side_effect=(
            ProcessedInput("image", b"image"),
            ProcessedInput("text", "good"),
        ),
    ):
        response = service.process_files(uploads)

    assert [item.filename for item in response.data] == ["bad.png", "good.txt"]
    assert [(item.status, item.reason) for item in response.data] == [
        ("failed", "Model endpoint failed to describe image"),
        ("success", None),
    ]
    model_client.embed_text.assert_called_once_with("good")
    qdrant_store.store_embedding.assert_called_once_with([0.4])


@pytest.mark.unit
def test_real_processing_returns_normal_response_when_all_files_fail() -> None:
    service, _, _, _ = make_service()

    response = service.process_files(
        (FileUpload("bad.bin", "application/octet-stream", b"\x1f\x8b\x08\x00"),),
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


@pytest.mark.unit
def test_file_processing_error_returns_safe_message() -> None:
    service = FileIngestionService(Mock(), Mock(), Mock())

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        side_effect=FileProcessingError("Unsupported file type"),
    ):
        response = service.process_files(
            (FileUpload("bad.bin", "application/octet-stream", b"bytes"),),
        )

    assert response.data[0].status == "failed"
    assert response.data[0].reason == "Unsupported file type"


@pytest.mark.unit
def test_qdrant_storage_error_returns_safe_message() -> None:
    _, _, model_client, qdrant_store = make_service()
    model_client.embed_text.return_value = [0.1]
    qdrant_store.store_embedding.side_effect = QdrantStorageError(
        "Qdrant storage failure"
    )
    service = FileIngestionService(Mock(), model_client, qdrant_store)

    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        return_value=ProcessedInput("text", "hello"),
    ):
        response = service.process_files(
            (FileUpload("note.txt", "text/plain", b"bytes"),),
        )

    assert response.data[0].status == "failed"
    assert response.data[0].reason == "Qdrant storage failure"


@pytest.mark.unit
def test_unexpected_error_logs_context_without_sensitive_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, _, _, _ = make_service()
    file_content = b"secret file content"
    filename = "private\nforged.txt"

    caplog.set_level(ERROR)
    with patch(
        "backend.app.file_embeddings.ingestion_service.process_file",
        side_effect=RuntimeError("secret provider response"),
    ):
        response = service.process_files(
            (FileUpload(filename, "text/plain", file_content),),
        )

    assert response.data[0].reason == "Processing failed"
    message = caplog.records[0].getMessage()
    assert filename not in message
    assert repr(filename) in message
    assert "RuntimeError" in message
    assert "secret file content" not in message
    assert "secret provider response" not in message


@pytest.mark.unit
def test_startup_ensures_collection_once() -> None:
    _, _, _, qdrant_store = make_service()
    service = FileIngestionService(Mock(), Mock(), qdrant_store)

    service.startup()

    qdrant_store.ensure_collection.assert_called_once_with()


@pytest.mark.unit
def test_startup_surfaces_qdrant_storage_error() -> None:
    qdrant_store = Mock()
    qdrant_store.ensure_collection.side_effect = QdrantStorageError(
        "Qdrant storage failure"
    )
    service = FileIngestionService(Mock(), Mock(), qdrant_store)

    with pytest.raises(QdrantStorageError, match="Qdrant storage failure"):
        service.startup()

    qdrant_store.ensure_collection.assert_called_once_with()
