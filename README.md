# OpenAI-Compatible File Embeddings

FastAPI service that accepts text, image, and PDF uploads, runs each image through a configurable vision-language model that returns a structured image description, embeds that description (or the raw text) via a configured text-embedding model, and stores only the resulting vectors in Qdrant. Raw vectors and image descriptions are never returned.

## Pipeline at a glance

```
upload ─▶ MIME detect ─▶ text/PDF? ─▶ raw text ─┐
                  │                              ├─▶ text embedding ─▶ Qdrant
                  └─ PNG/JPEG/WEBP? ─▶ structured description ─▶ formatted text ─┘
```

- Images (PNG/JPEG/WEBP) are sent to `DESCRIPTION_MODEL` via Instructor (JSON mode) and validated into a Pydantic `ImageDescription`. The description is converted into a deterministic multi-section string and embedded through `EMBEDDING_MODEL`.
- Text and PDF content is embedded directly through `EMBEDDING_MODEL`. PDFs use text extraction only.
- All vectors live in a single shared collection. Image and text vectors share the same embedding space.

## Local development

Prerequisites:

- Python 3.11 or newer
- `uv`
- `libmagic`
- Running Qdrant instance
- Running OpenAI-compatible endpoint that exposes both the vision-language model (`DESCRIPTION_MODEL`) and the text-embedding model (`EMBEDDING_MODEL`)

Install dependencies and copy configuration:

```bash
uv sync --extra dev
cp .env.example .env
```

Set `MODEL_ENDPOINT_URL`, `DESCRIPTION_MODEL`, `EMBEDDING_MODEL`, `QDRANT_URL`, and `QDRANT_VECTOR_SIZE`. Start the app:

```bash
uv run uvicorn backend.app.main:create_app --factory --reload
```

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MODEL_ENDPOINT_URL` | Yes | None | OpenAI-compatible base URL for the text-embedding model. |
| `MODEL_ENDPOINT_API_KEY` | No | Empty | Embedding endpoint API key. |
| `MODEL_REQUEST_TIMEOUT` | No | `30` | Model request timeout in seconds. |
| `DESCRIPTION_MODEL` | Yes | None | Vision-language model used to generate structured image descriptions (PNG/JPEG/WEBP). |
| `DESCRIPTION_ENDPOINT_URL` | Yes | None | OpenAI-compatible base URL for the description model. May differ from `MODEL_ENDPOINT_URL`. |
| `DESCRIPTION_ENDPOINT_API_KEY` | No | Empty | Description endpoint API key. |
| `EMBEDDING_MODEL` | Yes | None | Text-embedding model used for description text, raw text, and PDF text. |
| `UPLOAD_API_KEY` | No | Empty | Bearer key required for file uploads. When unset, uploads are accepted from loopback clients only. |
| `QDRANT_URL` | Yes | None | Qdrant URL. |
| `QDRANT_API_KEY` | No | Empty | Qdrant API key. |
| `QDRANT_COLLECTION` | No | `file_embeddings` | Qdrant collection name. |
| `QDRANT_VECTOR_SIZE` | Yes | None | Vector size; must match `EMBEDDING_MODEL` output. |
| `QDRANT_DISTANCE` | No | `Cosine` | Qdrant distance metric used when creating the collection. |

At startup, the app checks the configured Qdrant collection and creates it when missing using the configured vector size and distance metric.

## Docker Compose

Docker Desktop with Compose can run the app plus Qdrant:

```bash
cp .env.example .env
docker compose up --build
```

When the model API runs on the Docker Desktop host, set `MODEL_ENDPOINT_URL=http://host.docker.internal:8001/v1`. In other environments, use a URL reachable from the app container. Compose connects the app to Qdrant using service DNS.

`docker compose down` preserves the named `qdrant_storage` volume. `docker compose down -v` deletes local Qdrant data.

## Create file embeddings

`POST /v1/file-embeddings` accepts multipart form data with repeated `files` fields:

```bash
curl -X POST http://localhost:8000/v1/file-embeddings \
  -H "Authorization: Bearer $UPLOAD_API_KEY" \
  -F files=@README.md \
  -F files=@photo.png
```

The response contains one result per uploaded file:

```json
{
  "object": "list",
  "data": [
    {
      "filename": "README.md",
      "content_type": "text/markdown",
      "status": "success",
      "reason": null
    },
    {
      "filename": "bad.bin",
      "content_type": "application/octet-stream",
      "status": "failed",
      "reason": "Unsupported file type"
    }
  ]
}
```

Public items contain filename, content type, status (`success` or `failed`), and a safe reason when failed. Embedding vectors, Qdrant point IDs, image descriptions, image bytes, API keys, tracebacks, and local paths are never returned.

## Create text embeddings for vector search

`POST /v1/embeddings` accepts OpenAI-compatible JSON and returns query vectors without storing them in Qdrant. Use the same model used for uploaded files so vector dimensions and embedding space match.

```bash
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Authorization: Bearer $UPLOAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input":"search text"}'
```

`input` must be a single non-blank string. The response uses the configured `EMBEDDING_MODEL` for the `model` field. `usage` contains zero values because delegated embedding calls do not expose token counts.

OpenAI Python client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed",
)

response = client.embeddings.create(input="Your text string goes here")

print(response.data[0].embedding)
```

### Supported content

Type detection uses file bytes through `python-magic`; filename extensions do not determine type.

- UTF-8 text: `text/plain`, `text/csv`, `text/markdown`, `application/json`, `application/xml`, `text/yaml`, `text/x-yaml`, `text/html`, `text/css`, and `text/x-*`
- Images: PNG, JPEG, WEBP — routed through the description pipeline
- PDFs: text extraction only — routed through the text embedding path

Scanned PDFs are unsupported because OCR is out of scope.

### Limits and errors

- Maximum 10 files per request
- Maximum 25 MB per file
- Maximum 250 MB aggregate request body
- Images exceeding 100 million pixels are rejected
- Uploads require `Authorization: Bearer $UPLOAD_API_KEY` when configured, and are rate-limited to 60 requests per minute per client address
- Missing files or more than 10 files return HTTP 400
- Empty, oversized, unsupported, invalid, model-failed, or storage-failed files return per-file errors with HTTP 200 when the request itself is valid

## Health

```bash
curl http://localhost:8000/health
```

Healthy response:

```json
{"status":"ok","qdrant":"ok","model":"ok"}
```

The `model` field reports `ok` only when both `DESCRIPTION_MODEL` and `EMBEDDING_MODEL` are reachable from the configured endpoint. The overall status becomes `degraded` when any of the three dependencies (description, embedding, Qdrant) reports unavailable.

## Privacy

- Image bytes leave the app only as part of the description request to `MODEL_ENDPOINT_URL`.
- Image descriptions are transient. They are held in memory only long enough to be embedded, then discarded. Descriptions are never logged, persisted, returned in API responses, or stored as Qdrant payload.
- Stored Qdrant points carry the vector only — no payload, no filename, no metadata.

## Security

File uploads require `UPLOAD_API_KEY` bearer authentication (when configured) and use in-memory per-client rate limiting (60 requests/min). Aggregate request bodies are bounded at 250 MB. Compose publishes app and Qdrant ports on loopback by default. Keep services behind trusted/private networks or an authenticated gateway in production.

For production deployments behind a reverse proxy (e.g. Nginx, Traefik, Caddy, or AWS ALB), enforce ingress request body limits (such as Nginx `client_max_body_size 250m;`) to bound chunked uploads before body spooling occurs at the ASGI application server level.

Health checks use low-cost model listing and do not submit embedding or description requests.