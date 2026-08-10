import pytest
from pydantic import ValidationError

from backend.app.api.schemas.file_embeddings import (
    ErrorDetail,
    FileEmbeddingItem,
    FileEmbeddingResponse,
)
from backend.app.api.schemas.health import HealthResponse


@pytest.mark.unit
def test_success_item_has_empty_error() -> None:
    item = FileEmbeddingItem(
        filename="report.txt",
        content_type="text/plain",
        error="",
    )

    assert item.filename == "report.txt"
    assert item.error == ""


@pytest.mark.unit
def test_error_item_preserves_safe_message() -> None:
    item = FileEmbeddingItem(
        filename="bad.bin",
        content_type="application/octet-stream",
        error="Unsupported file type",
    )

    assert item.error == "Unsupported file type"


@pytest.mark.unit
def test_response_uses_list_object_marker() -> None:
    response = FileEmbeddingResponse(
        object="list",
        data=[FileEmbeddingItem(filename="x.txt", content_type="text/plain")],
    )

    assert response.object == "list"
    assert len(response.data) == 1


@pytest.mark.unit
def test_error_detail_requires_message_and_type() -> None:
    with pytest.raises(ValidationError):
        ErrorDetail(message="only message")


@pytest.mark.unit
def test_health_response_contains_dependency_statuses() -> None:
    response = HealthResponse(status="ok", qdrant="ok", model="ok")

    assert response.model == "ok"
