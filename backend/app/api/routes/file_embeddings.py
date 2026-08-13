"""File embedding API routes."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import StringConstraints

from backend.app.api.schemas.file_embeddings import FileEmbeddingResponse
from backend.app.file_embeddings.service import FileEmbeddingService, FileUpload
from backend.app.file_processing.service import MAX_FILE_SIZE
from backend.app.security import (
    MAX_REQUEST_SIZE,
    reject_oversized_request,
    require_upload_access,
)

MAX_FILES = 10
MAX_AGGREGATE_UPLOAD_SIZE = MAX_REQUEST_SIZE

router = APIRouter()


_FILE_EMBEDDING_SERVICE: FileEmbeddingService | None = None


def get_file_embedding_service() -> FileEmbeddingService:
    """Return the configured file embedding service."""
    if _FILE_EMBEDDING_SERVICE is None:
        raise RuntimeError("File embedding service is not configured")
    return _FILE_EMBEDDING_SERVICE


def authorize_upload(request: Request) -> None:
    """Apply request-size, API-key, and rate-limit controls."""
    reject_oversized_request(request)
    require_upload_access(request)


@router.post(
    "/v1/file-embeddings",
    response_model=FileEmbeddingResponse,
    status_code=status.HTTP_200_OK,
)
def create_file_embeddings(
    model: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
        Form(...),
    ],
    files: list[UploadFile] | None = File(default=None),
    service: FileEmbeddingService = Depends(get_file_embedding_service),
) -> FileEmbeddingResponse:
    """Create embeddings for uploaded files."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"A maximum of {MAX_FILES} files is allowed",
            )

        uploads: list[FileUpload] = []
        aggregate_size = 0
        for file in files:
            remaining = MAX_AGGREGATE_UPLOAD_SIZE - aggregate_size
            content = file.file.read(min(MAX_FILE_SIZE + 1, remaining + 1))
            aggregate_size += len(content)
            uploads.append(
                FileUpload(
                    filename=file.filename or "",
                    content_type=file.content_type or "",
                    content=content,
                )
            )
            if aggregate_size > MAX_AGGREGATE_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Request exceeds 250 MB limit",
                )

        return service.process_files(uploads, model)
    finally:
        for file in files:
            file.file.close()
