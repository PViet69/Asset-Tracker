"""OpenAI-compatible text embedding API schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_EMBEDDING_TEXT_LENGTH = 8_192

EmbeddingText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_EMBEDDING_TEXT_LENGTH,
    ),
]


class TextEmbeddingCreate(BaseModel):
    """Validated configured-model text embedding request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: EmbeddingText


class TextEmbeddingData(BaseModel):
    """One OpenAI-compatible embedding result."""

    model_config = ConfigDict(frozen=True)

    object: Literal["embedding"] = "embedding"
    embedding: list[float]
    index: int


class TextEmbeddingUsage(BaseModel):
    """Token usage unavailable from delegated embedding requests."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    total_tokens: int = 0


class TextEmbeddingPublic(BaseModel):
    """OpenAI-compatible embedding response."""

    model_config = ConfigDict(frozen=True)

    object: Literal["list"] = "list"
    data: list[TextEmbeddingData]
    model: str
    usage: TextEmbeddingUsage = Field(default_factory=TextEmbeddingUsage)
