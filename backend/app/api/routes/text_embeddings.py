"""OpenAI-compatible text embedding API route."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.dependencies import get_file_ingestion_service
from backend.app.api.schemas.text_embeddings import (
    TextEmbeddingCreate,
    TextEmbeddingData,
    TextEmbeddingPublic,
)
from backend.app.exceptions import ModelEndpointError, ModelNotFoundError
from backend.app.file_embeddings.ingestion_service import FileIngestionService

router = APIRouter()


@router.post(
    "/v1/embeddings",
    response_model=TextEmbeddingPublic,
    status_code=status.HTTP_200_OK,
)
def create_text_embeddings(
    payload: TextEmbeddingCreate,
    service: FileIngestionService = Depends(get_file_ingestion_service),
) -> TextEmbeddingPublic:
    """Create query embeddings without storing them in Qdrant."""
    try:
        vector = service.embed_text(payload.input)
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.safe_message,
        ) from exc
    except ModelEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc

    return TextEmbeddingPublic(
        data=[TextEmbeddingData(embedding=vector, index=0)],
        model=service.embedding_model,
    )
