from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.health import HealthDependencies
from backend.app.file_embeddings.ingestion_service import FileIngestionService
from backend.app.integrations.model_client import ModelClient
from backend.app.integrations.qdrant_store import QdrantStore
from backend.app.main import create_app
from backend.app.model.description_client import ImageDescriptionClient


@pytest.fixture
def app() -> FastAPI:
    """Return a fresh FastAPI application instance."""
    service = Mock(spec=FileIngestionService)
    service.embedding_model = "embedding-model"
    description_client = Mock(spec=ImageDescriptionClient)
    model_client = Mock(spec=ModelClient)
    qdrant_store = Mock(spec=QdrantStore)
    description_client.check_health.return_value = "ok"
    model_client.check_health.return_value = "ok"
    qdrant_store.check_health.return_value = "ok"
    health_dependencies = HealthDependencies(
        description_client=description_client,
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
