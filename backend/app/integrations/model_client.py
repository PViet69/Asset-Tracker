"""OpenAI-compatible model adapter for embedding text and image files."""

import base64
import logging
from typing import Protocol

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
        try:
            response = self._client.embeddings.create(model=model, input=text)
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

        return self._extract_embedding(response)

    def embed_image(self, image_bytes: bytes, model: str) -> list[float]:
        """Embed image bytes and return the numeric vector.

        Image data is base64-encoded into a ``data:image/png;base64,`` URI,
        matching the model endpoint contract.
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"

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
            self._client.embeddings.create(model="health-check", input="ping")
        except Exception:  # noqa: BLE001
            return "unavailable"
        return "ok"

    @staticmethod
    def _extract_embedding(response: object) -> list[float]:
        """Validate and extract the embedding vector from the SDK response."""
        data = getattr(response, "data", [])
        if not data or len(data) != 1:
            raise ModelEndpointError("Model endpoint returned an invalid embedding")

        embedding = getattr(data[0], "embedding", None)
        if (
            not embedding
            or not isinstance(embedding, list)
            or len(embedding) == 0
            or not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in embedding
            )
        ):
            raise ModelEndpointError("Model endpoint returned an invalid embedding")

        return list(embedding)
