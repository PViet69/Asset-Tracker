"""Health check API route."""

from dataclasses import dataclass

from fastapi import APIRouter, Depends, status

from backend.app.api.schemas.health import HealthResponse
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore

router = APIRouter()


@dataclass(frozen=True)
class HealthDependencies:
    """Dependencies used by the health check."""

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
    """Report model and Qdrant availability."""
    model_status = dependencies.model_client.check_health()
    qdrant_status = dependencies.qdrant_store.check_health()
    overall_status = "ok" if model_status == qdrant_status == "ok" else "degraded"
    return HealthResponse(
        status=overall_status,
        qdrant=qdrant_status,
        model=model_status,
    )
