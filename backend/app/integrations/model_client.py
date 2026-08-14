"""OpenAI-compatible model adapter for embedding text and image files."""

import base64
import logging
from typing import Protocol

import magic

from backend.app.config import Settings
from backend.app.exceptions import ModelEndpointError
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

logger = logging.getLogger(__name__)


class ModelClient(Protocol):
    """Protocol for embedding text and images via an external model."""

    def embed_text(self, text: str, model: str) -> list[float]: ...
    def embed_image(self, image_bytes: bytes, model: str) -> list[float]: ...
    def check_health(self) -> str: ...


class OpenAICompatibleModelClient:
    """ModelClient backed by any OpenAI-compatible HTTP endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            base_url=settings.MODEL_ENDPOINT_URL,
            api_key=settings.MODEL_ENDPOINT_API_KEY or "not-needed",
            timeout=settings.MODEL_REQUEST_TIMEOUT,
        )

    @classmethod
    def from_client(cls, client: OpenAI) -> "OpenAICompatibleModelClient":
        """Construct with a pre-built OpenAI client (useful for testing with mocks)."""
        instance = cls.__new__(cls)
        instance._client = client
        return instance

    def embed_text(self, text: str, model: str) -> list[float]:
        """Embed a text string and return the numeric vector."""
        response = self._create_text_embeddings(text, model)
        return self._extract_embedding(response)

    def _create_text_embeddings(
        self,
        input_value: str,
        model: str,
    ) -> object:
        """Create text embeddings and map SDK errors to domain errors."""
        try:
            return self._client.embeddings.create(model=model, input=input_value)
        except APITimeoutError:
            logger.error("Model endpoint timed out for text embedding", exc_info=True)
            raise ModelEndpointError("Model endpoint timed out")
        except APIConnectionError as exc:
            logger.error(
                "Model endpoint connection failed for text embedding", exc_info=True
            )
            raise ModelEndpointError("Model endpoint rejected input") from exc
        except APIError as exc:
            logger.error("Model endpoint rejected text embedding input", exc_info=True)
            raise ModelEndpointError("Model endpoint rejected input") from exc

    def embed_image(self, image_bytes: bytes, model: str) -> list[float]:
        """Embed image bytes and return the numeric vector.

        Image data is base64-encoded into a data URI using detected MIME type.
        Unknown image types default to PNG for compatibility.
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        mime_type = magic.from_buffer(image_bytes, mime=True)
        if mime_type not in {"image/jpeg", "image/webp", "image/png"}:
            mime_type = "image/png"
        data_url = f"data:{mime_type};base64,{b64}"

        try:
            response = self._client.embeddings.create(model=model, input=data_url)
        except APITimeoutError:
            logger.error("Model endpoint timed out for image embedding", exc_info=True)
            raise ModelEndpointError("Model endpoint timed out")
        except APIConnectionError as exc:
            logger.error(
                "Model endpoint connection failed for image embedding", exc_info=True
            )
            raise ModelEndpointError("Model endpoint rejected input") from exc
        except APIError as exc:
            logger.error("Model endpoint rejected image embedding input", exc_info=True)
            raise ModelEndpointError("Model endpoint rejected input") from exc

        return self._extract_embedding(response)

    def check_health(self) -> str:
        """Return 'ok' if the model endpoint responds, else 'unavailable'."""
        try:
            self._client.models.list()
        except Exception:  # noqa: BLE001
            return "unavailable"
        return "ok"

    @classmethod
    def _extract_embedding(cls, response: object) -> list[float]:
        """Validate and extract one embedding vector from the SDK response."""
        return cls._extract_embeddings(response, 1)[0]

    @staticmethod
    def _extract_embeddings(
        response: object,
        expected_count: int,
    ) -> list[list[float]]:
        """Validate and extract embedding vectors from the SDK response."""
        data = getattr(response, "data", [])
        if not data or len(data) != expected_count:
            raise ModelEndpointError("Model endpoint returned an invalid embedding")

        vectors: list[list[float]] = []
        for item in data:
            embedding = getattr(item, "embedding", None)
            if (
                not embedding
                or not isinstance(embedding, list)
                or not all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in embedding
                )
            ):
                raise ModelEndpointError("Model endpoint returned an invalid embedding")
            vectors.append(list(embedding))
        return vectors
