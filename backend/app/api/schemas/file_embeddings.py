from typing import Literal

from pydantic import BaseModel, ConfigDict


class FileEmbeddingItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    content_type: str = ""
    error: str = ""


class FileEmbeddingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    object: Literal["list"] = "list"
    data: list[FileEmbeddingItem]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: str
    type: str
    filename: str = ""


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    error: ErrorDetail
