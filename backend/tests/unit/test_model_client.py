from unittest.mock import Mock

import httpx
import pytest

from backend.app.exceptions import ModelEndpointError
from backend.app.integrations.model_client import OpenAICompatibleModelClient
from openai import APIConnectionError, APIError, APITimeoutError


def test_embed_text_returns_embedding_from_sdk_response() -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[0.1, 0.2])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    assert client.embed_text("hello", "model-a") == [0.1, 0.2]
    sdk.embeddings.create.assert_called_once_with(model="model-a", input="hello")


@pytest.mark.parametrize(
    ("image_bytes", "expected_mime"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"png-bytes", "image/png"),
        (b"\xff\xd8\xff\xe0" + b"jpeg-bytes", "image/jpeg"),
        (b"RIFF" + b"\x00" * 4 + b"WEBP" + b"webp-bytes", "image/webp"),
    ],
)
def test_embed_image_preserves_detected_image_mime(
    image_bytes: bytes, expected_mime: str
) -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[0.3])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    result = client.embed_image(image_bytes, "vision-model")

    assert result == [0.3]
    call = sdk.embeddings.create.call_args.kwargs
    assert call["model"] == "vision-model"
    assert call["input"].startswith(f"data:{expected_mime};base64,")


def test_embed_image_defaults_unknown_mime_to_png() -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[0.3])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    client.embed_image(b"png-bytes", "vision-model")

    assert sdk.embeddings.create.call_args.kwargs["input"].startswith(
        "data:image/png;base64,"
    )


def test_model_timeout_becomes_safe_domain_error() -> None:
    sdk = Mock()
    sdk.embeddings.create.side_effect = APITimeoutError(
        request=httpx.Request("POST", "https://model.example/embeddings")
    )
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError) as exc_info:
        client.embed_text("hello", "model-a")

    assert str(exc_info.value) == "Model endpoint timed out"


def test_model_api_error_becomes_safe_domain_error() -> None:
    sdk = Mock()
    sdk.embeddings.create.side_effect = APIError(
        "secret provider detail",
        request=httpx.Request("POST", "https://model.example/embeddings"),
        body=None,
    )
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError) as exc_info:
        client.embed_text("hello", "model-a")

    assert str(exc_info.value) == "Model endpoint rejected input"
    assert "secret provider detail" not in str(exc_info.value)


def test_embed_text_empty_embedding_raises() -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=[])]
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError, match="invalid embedding"):
        client.embed_text("hello", "model-a")


def test_embed_text_no_items_raises() -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = []
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError, match="invalid embedding"):
        client.embed_text("hello", "model-a")


@pytest.mark.parametrize("embedding", [["not-numeric"], [True]])
def test_embed_text_non_numeric_embedding_raises(embedding: list[object]) -> None:
    sdk = Mock()
    sdk.embeddings.create.return_value.data = [Mock(embedding=embedding)]
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError, match="invalid embedding"):
        client.embed_text("hello", "model-a")


def test_embed_image_timeout_raises() -> None:
    sdk = Mock()
    sdk.embeddings.create.side_effect = APITimeoutError(
        request=httpx.Request("POST", "https://model.example/embeddings")
    )
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError) as exc_info:
        client.embed_image(b"img", "model-b")

    assert str(exc_info.value) == "Model endpoint timed out"


def test_embed_image_connection_error_raises() -> None:
    sdk = Mock()
    sdk.embeddings.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://model.example/embeddings")
    )
    client = OpenAICompatibleModelClient.from_client(sdk)

    with pytest.raises(ModelEndpointError, match="^Model endpoint rejected input$"):
        client.embed_image(b"img", "model-b")


def test_check_health_ok() -> None:
    sdk = Mock()
    client = OpenAICompatibleModelClient.from_client(sdk)

    assert client.check_health() == "ok"
    sdk.models.list.assert_called_once_with()


def test_check_health_unavailable() -> None:
    sdk = Mock()
    sdk.models.list.side_effect = ConnectionError()
    client = OpenAICompatibleModelClient.from_client(sdk)

    assert client.check_health() == "unavailable"
    sdk.models.list.assert_called_once_with()
