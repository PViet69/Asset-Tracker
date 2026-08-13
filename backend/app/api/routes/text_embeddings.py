"""OpenAI-compatible text embedding API route."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.dependencies import get_file_embedding_service
from backend.app.api.schemas.text_embeddings import (
    TextEmbeddingCreate,
    TextEmbeddingData,
    TextEmbeddingPublic,
)
from backend.app.exceptions import ModelEndpointError
from backend.app.file_embeddings.service import FileEmbeddingService

router = APIRouter()


@router.post(
    "/v1/embeddings",
    response_model=TextEmbeddingPublic,
    status_code=status.HTTP_200_OK,
)
def create_text_embeddings(
    payload: TextEmbeddingCreate,
    service: FileEmbeddingService = Depends(get_file_embedding_service),
) -> TextEmbeddingPublic:
    """Create query embeddings without storing them in Qdrant."""
    try:
        vectors = service.embed_texts(payload.input, payload.model)
    except ModelEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.safe_message,
        ) from exc

    data = [
        TextEmbeddingData(embedding=vector, index=index)
        for index, vector in enumerate(vectors)
    ]
    return TextEmbeddingPublic(data=data, model=payload.model)
