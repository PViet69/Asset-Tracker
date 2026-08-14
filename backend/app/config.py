from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
        extra="ignore",
    )

    MODEL_ENDPOINT_URL: str
    MODEL_ENDPOINT_API_KEY: str | None = None
    MODEL_REQUEST_TIMEOUT: float = Field(default=30, gt=0)


    QDRANT_URL: str
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "file_embeddings"
    QDRANT_VECTOR_SIZE: int = Field(gt=0)
    QDRANT_DISTANCE: str = "Cosine"
