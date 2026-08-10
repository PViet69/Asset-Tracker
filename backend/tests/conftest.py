from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.health import HealthDependencies
from backend.app.file_embeddings.service import FileEmbeddingService
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore
from backend.app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    """Return a fresh FastAPI application instance."""
    service = Mock(spec=FileEmbeddingService)
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    model_client.check_health.return_value = "ok"
    qdrant_store.check_health.return_value = "ok"
    health_dependencies = HealthDependencies(
        model_client=model_client,
        qdrant_store=qdrant_store,
    )
    return create_app(
        service=service,
        health_dependencies=health_dependencies,
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Return a TestClient for the application."""
    with TestClient(app) as test_client:
        yield test_client
