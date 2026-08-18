"""Health check API route."""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, status

from backend.app.api.schemas.health import HealthResponse
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore
from backend.app.model.description_client import ImageDescriptionClient

router = APIRouter()


@dataclass(frozen=True)
class HealthDependencies:
    """Dependencies used by the health check."""

    description_client: ImageDescriptionClient
    model_client: ModelClient
    qdrant_store: QdrantStore


_HEALTH_DEPENDENCIES: HealthDependencies | None = None


def get_health_dependencies() -> HealthDependencies:
    """Return configured health check dependencies."""
    if _HEALTH_DEPENDENCIES is None:
        raise RuntimeError("Health dependencies are not configured")
    return _HEALTH_DEPENDENCIES


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health(
    dependencies: HealthDependencies = Depends(get_health_dependencies),
) -> HealthResponse:
    """Report image description, embedding, and Qdrant availability."""
    description_status = dependencies.description_client.check_health()
    model_status = dependencies.model_client.check_health()
    qdrant_status = dependencies.qdrant_store.check_health()
    model_status_combined = (
        "unavailable" if "unavailable" in (description_status, model_status) else "ok"
    )
    overall_status = (
        "ok"
        if description_status == model_status == qdrant_status == "ok"
        else "degraded"
    )
    return HealthResponse(
        status=overall_status,
        qdrant=qdrant_status,
        model=model_status_combined,
    )
