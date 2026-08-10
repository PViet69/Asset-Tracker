"""File embedding API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import StringConstraints

from backend.app.api.schemas.file_embeddings import FileEmbeddingResponse
from backend.app.file_embeddings.service import FileEmbeddingService, FileUpload
from backend.app.file_processing.service import MAX_FILE_SIZE

MAX_FILES = 10

router = APIRouter()


_FILE_EMBEDDING_SERVICE: FileEmbeddingService | None = None


def get_file_embedding_service() -> FileEmbeddingService:
    """Return the configured file embedding service."""
    if _FILE_EMBEDDING_SERVICE is None:
        raise RuntimeError("File embedding service is not configured")
    return _FILE_EMBEDDING_SERVICE


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
        for file in files:
            content = file.file.read(MAX_FILE_SIZE + 1)
            uploads.append(
                FileUpload(
                    filename=file.filename or "",
                    content_type=file.content_type or "",
                    content=content,
                )
            )

        return service.process_files(uploads, model)
    finally:
        for file in files:
            file.file.close()
