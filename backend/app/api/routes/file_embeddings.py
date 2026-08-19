"""File embedding API routes."""

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

from backend.app.api.dependencies import get_file_ingestion_service
from backend.app.api.schemas.file_embeddings import FileEmbeddingResponse
from backend.app.exceptions import ModelNotFoundError
from backend.app.file_embeddings.ingestion_service import (
    FileIngestionService,
    FileUpload,
)
from backend.app.file_processing.service import MAX_FILE_SIZE
from backend.app.security import (
    MAX_REQUEST_SIZE,
    reject_oversized_request,
    require_upload_access,
)

MAX_FILES = 10
MAX_AGGREGATE_UPLOAD_SIZE = MAX_REQUEST_SIZE

router = APIRouter()


def authorize_upload(request: Request) -> None:
    """Apply request-size, authentication, and rate-limit controls."""
    reject_oversized_request(request)
    require_upload_access(request)


@router.post(
    "/v1/file-embeddings",
    response_model=FileEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(authorize_upload)],
)
def create_file_embeddings(
    files: list[UploadFile] | None = File(default=None),
    file_path: list[str] | None = Form(default=None),
    service: FileIngestionService = Depends(get_file_ingestion_service),
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

        paths: list[str] = list(file_path) if file_path else []
        if len(paths) > len(files):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"`file_path` has more entries than `files` "
                    f"({len(paths)} paths for {len(files)} files)"
                ),
            )
        while len(paths) < len(files):
            paths.append("")

        uploads: list[FileUpload] = []
        aggregate_size = 0
        for index, file in enumerate(files):
            remaining = MAX_AGGREGATE_UPLOAD_SIZE - aggregate_size
            content = file.file.read(min(MAX_FILE_SIZE + 1, remaining + 1))
            aggregate_size += len(content)
            uploads.append(
                FileUpload(
                    filename=file.filename or "",
                    content_type=file.content_type or "",
                    content=content,
                    file_path=paths[index],
                )
            )
            if aggregate_size > MAX_AGGREGATE_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Request exceeds 250 MB limit",
                )

        try:
            return service.process_files(tuple(uploads))
        except ModelNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=exc.safe_message,
            ) from exc
    finally:
        for file in files:
            file.file.close()
