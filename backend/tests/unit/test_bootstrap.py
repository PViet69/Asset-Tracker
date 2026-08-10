from fastapi import FastAPI

from backend.app.main import create_app


def test_create_app_returns_fastapi_application() -> None:
    app: FastAPI = create_app()
    assert app.title == "OpenAI File Embeddings"
