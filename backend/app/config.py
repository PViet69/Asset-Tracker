from typing import Annotated

from pydantic import Field, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NonBlankSetting = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


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
    UPLOAD_API_KEY: str | None = None
    DESCRIPTION_MODEL: NonBlankSetting
    DESCRIPTION_ENDPOINT_URL: str | None = None
    DESCRIPTION_ENDPOINT_API_KEY: str | None = None
    EMBEDDING_MODEL: NonBlankSetting

    QDRANT_URL: str
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "file_embeddings"
    QDRANT_VECTOR_SIZE: int = Field(gt=0)
    QDRANT_DISTANCE: str = "Cosine"

    @model_validator(mode="after")
    def _validate_description_endpoint(self) -> "Settings":
        missing = [
            name
            for name, value in (
                ("DESCRIPTION_ENDPOINT_URL", self.DESCRIPTION_ENDPOINT_URL),
                ("DESCRIPTION_ENDPOINT_API_KEY", self.DESCRIPTION_ENDPOINT_API_KEY),
            )
            if value is None
        ]
        if missing:
            joined = " and ".join(missing)
            raise ValueError(
                f"{joined} must be set when DESCRIPTION_MODEL is configured"
            )
        return self
