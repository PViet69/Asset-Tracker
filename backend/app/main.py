from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request

from backend.app.api.routes.file_embeddings import (
    get_file_embedding_service,
)
from backend.app.api.routes.file_embeddings import (
    router as file_embeddings_router,
)
from backend.app.api.routes.health import (
    HealthDependencies,
    get_health_dependencies,
)
from backend.app.api.routes.health import (
    router as health_router,
)
from backend.app.config import Settings
from backend.app.file_embeddings.service import FileEmbeddingService
from backend.app.integrations.model_client import OpenAICompatibleModelClient
from backend.app.integrations.qdrant_store import QdrantEmbeddingStore


@dataclass(frozen=True)
class _UnavailableHealthDependency:
    def check_health(self) -> str:
        return "unavailable"


def create_app(
    service: FileEmbeddingService | None = None,
    health_dependencies: HealthDependencies | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        effective_service = service
        effective_health_dependencies = health_dependencies

        if effective_service is None:
            settings = Settings()
            model_client = OpenAICompatibleModelClient(settings)
            qdrant_store = QdrantEmbeddingStore(settings)
            effective_service = FileEmbeddingService(model_client, qdrant_store)
            if effective_health_dependencies is None:
                effective_health_dependencies = HealthDependencies(
                    model_client=model_client,
                    qdrant_store=qdrant_store,
                )
        elif effective_health_dependencies is None:
            unavailable = _UnavailableHealthDependency()
            effective_health_dependencies = HealthDependencies(
                model_client=unavailable,
                qdrant_store=unavailable,
            )

        assert effective_service is not None
        assert effective_health_dependencies is not None
        effective_service.startup()
        application.state.file_embedding_service = effective_service
        application.state.health_dependencies = effective_health_dependencies
        try:
            yield
        finally:
            application.state._state.pop("file_embedding_service", None)
            application.state._state.pop("health_dependencies", None)

    app = FastAPI(
        title="OpenAI File Embeddings",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(file_embeddings_router)
    app.include_router(health_router)

    def provide_file_embedding_service(request: Request) -> FileEmbeddingService:
        return request.app.state.file_embedding_service

    def provide_health_dependencies(request: Request) -> HealthDependencies:
        return request.app.state.health_dependencies

    app.dependency_overrides[get_file_embedding_service] = (
        provide_file_embedding_service
    )
    app.dependency_overrides[get_health_dependencies] = provide_health_dependencies
    return app
