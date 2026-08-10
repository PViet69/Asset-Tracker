# OpenAI-Compatible File Embeddings

FastAPI service that accepts text, image, and PDF uploads, creates one embedding per successful file through a configurable OpenAI-compatible endpoint, and stores embeddings in Qdrant. Raw vectors are never returned.

## Local development

Prerequisites:

- Python 3.11 or newer
- `uv`
- `libmagic`
- Running Qdrant instance
- Running OpenAI-compatible embeddings endpoint

Install dependencies and copy configuration:

```bash
uv sync --extra dev
cp .env.example .env
```

Set `MODEL_ENDPOINT_URL`, `QDRANT_URL`, and `QDRANT_VECTOR_SIZE` for your services. Start app:

```bash
uv run uvicorn backend.app.main:create_app --factory --reload
```

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MODEL_ENDPOINT_URL` | Yes | None | OpenAI-compatible embeddings API base URL. |
| `MODEL_ENDPOINT_API_KEY` | No | Empty | Model endpoint API key. |
| `MODEL_REQUEST_TIMEOUT` | No | `30` | Model request timeout in seconds. |
| `QDRANT_URL` | Yes | None | Qdrant URL. |
| `QDRANT_API_KEY` | No | Empty | Qdrant API key. |
| `QDRANT_COLLECTION` | No | `file_embeddings` | Qdrant collection name. |
| `QDRANT_VECTOR_SIZE` | Yes | None | Vector size; must match model output. |
| `QDRANT_DISTANCE` | No | `Cosine` | Qdrant distance metric used when creating collection. |

At startup, app checks configured Qdrant collection and creates it when missing using configured vector size and distance metric.

## Docker Compose

Docker Desktop with Compose can run app plus Qdrant:

```bash
cp .env.example .env
docker compose up --build
```

When model API runs on Docker Desktop host, set `MODEL_ENDPOINT_URL=http://host.docker.internal:8001/v1`. In other environments, use URL reachable from app container. Compose connects app to Qdrant using service DNS.

`docker compose down` preserves named `qdrant_storage` volume. `docker compose down -v` deletes local Qdrant data.

## Create file embeddings

`POST /v1/file-embeddings` accepts multipart form data with one `model` field and repeated `files` fields:

```bash
curl -X POST http://localhost:8000/v1/file-embeddings \
  -F model=text-embedding-3-small \
  -F files=@README.md \
  -F files=@photo.png
```

Response contains one result per uploaded file:

```json
{
  "object": "list",
  "data": [
    {
      "filename": "README.md",
      "content_type": "text/markdown",
      "error": ""
    },
    {
      "filename": "bad.bin",
      "content_type": "application/octet-stream",
      "error": "Unsupported file type"
    }
  ]
}
```

Public items contain only filename, content type, and safe error text. Embedding vectors, Qdrant point IDs, API keys, tracebacks, and local paths are not returned.

### Supported content

Type detection uses file bytes through `python-magic`; filename extensions do not determine type.

- UTF-8 text: `text/plain`, `text/csv`, `text/markdown`, `application/json`, `application/xml`, `text/yaml`, `text/x-yaml`, `text/html`, `text/css`, and `text/x-*`
- Images: PNG, JPEG, WEBP
- PDFs: text extraction only

Scanned PDFs are unsupported because OCR is out of scope.

### Limits and errors

- Maximum 10 files per request
- Maximum 25 MB per file
- Missing files or more than 10 files return HTTP 400
- Missing or blank `model` returns HTTP 422
- Empty, oversized, unsupported, invalid, model-failed, or storage-failed files return per-file errors with HTTP 200 when request itself is valid

## Health

```bash
curl http://localhost:8000/health
```

Healthy response:

```json
{"status":"ok","qdrant":"ok","model":"ok"}
```

Overall status becomes `degraded` when Qdrant or model endpoint reports unavailable.

## Security

Service has no built-in authentication. Deploy only on trusted/private networks, or place behind gateway providing authentication and rate limiting.
