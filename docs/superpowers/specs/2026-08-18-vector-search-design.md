# Vector Search for Image Embeddings — Design

Date: 2026-08-18
Status: Approved
Branch: docs/vector-search

## Summary

Add a `POST /v1/search` endpoint that embeds a text query with the configured
`EMBEDDING_MODEL` and returns the most similar stored **image** embedding
points from Qdrant, including the stored image description text. To support
this, image ingestion starts storing a payload alongside each vector.

Text/PDF ingestion is unchanged (vector-only, no payload) — chunking and text
search are a separate future task.

## Goals

- Search stored image embeddings by natural-language query.
- Return point ID, cosine similarity score, filename, content type, and the
  stored description text for each hit — enough to debug why an image matched.
- Enforce a fixed score threshold via configuration.

## Non-Goals

- Searching text/PDF embeddings (chunking strategy comes later).
- Migration of legacy payload-less points (operator deletes them manually).
- Snippet/truncation support (descriptions are bounded by the description
  pipeline, so no truncation is needed).
- Per-request threshold override (fixed config value only).

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SEARCH_THRESHOLD` | No | `None` | Minimum cosine similarity for search hits. Required at request time; search errors when unset. |

- `Settings.SEARCH_THRESHOLD: float | None = None` (no default).
- Startup validation: when set, must satisfy `0 <= value <= 1`; otherwise
  `SettingsError` fails fast, matching existing config validation patterns.
- Uploads and embeddings work without it; only `/v1/search` requires it.
- `.env.example` gains a `SEARCH_THRESHOLD=` line with a comment.

## Payload Schema (image points only)

Each image point gets a Qdrant payload:

```json
{
  "filename": "<upload filename as-is>",
  "file_type": "<MIME type>",
  "content": "<description text, same string that was embedded>",
}
```

- Text/PDF points keep `payload=None`. If matched by search, their payload
  fields come back as `null`.

## Privacy Policy Change

The current README states image descriptions are transient and never
persisted. This design deliberately overrides that: descriptions are now
stored as Qdrant payload so search results can surface them for debugging.
The README privacy section is rewritten accordingly.

## Components

### `backend/app/integrations/qdrant_store.py`

- `QdrantStore` protocol and `QdrantEmbeddingStore`:
  - `store_embedding(embedding: list[float], payload: dict | None = None) -> str`
    — signature extended; existing vector-only call sites keep working.
  - New `search(vector: list[float], limit: int, score_threshold: float) -> list[SearchHit]`
    where `SearchHit` is a frozen dataclass: `point_id: str`, `score: float`,
    `payload: dict`.
    - Uses Qdrant `search`/`query_points` with
      `score_threshold=score_threshold` (native Qdrant cutoff). No payload
      filter — all points are searchable.
    - Results ordered by score descending (Qdrant native ordering).
    - Any client exception is wrapped in `QdrantStorageError("Qdrant storage failure")`,
      logging the cause server-side — same pattern as `store_embedding`.

### `backend/app/file_embeddings/ingestion_service.py`

- `_process_one`: for the image branch, build the payload dict (filename,
  file_type, description text) and pass it to
  `store_embedding`. Text/PDF branch unchanged.
- New `search(query: str, limit: int) -> VectorSearchResponse`:
  - Raises `SettingsError("Search is not configured")` when
    `SEARCH_THRESHOLD` is unset.
  - Embeds `query` via `ModelClient.embed_text` (same path as
    `POST /v1/embeddings`).
  - Calls `store.search(vector, limit, settings.SEARCH_THRESHOLD)`.
  - Maps hits to public items (below). Defensive: a hit whose payload is
    missing a field maps that field to `None` rather than failing.
  - Service gains `Settings` access for the threshold (constructor parameter,
  matching existing dependency wiring in `create_app`).

### API

New route `POST /v1/search` in `backend/app/api/routes/vector_search.py`
with schemas in `backend/app/api/schemas/vector_search.py`.

Request:

```json
{"query": "a red sports car", "limit": 10}
```

- `query`: required, single non-blank string.
- `limit`: optional integer, default 10, valid range 1–100.
- Invalid request bodies → HTTP 422 via Pydantic validation (consistent with
  existing FastAPI behavior).

Response:

```json
{
  "object": "list",
  "data": [
    {
      "point_id": "3f2b...",
      "score": 0.87,
      "filename": "photo.png",
      "file_type": "image/png",
      "content": "Description text...",
    }
  ]
}
```

Empty matches return `"data": []` with HTTP 200.

Auth and limits: reuse the existing `require_upload_access` dependency —
`UPLOAD_API_KEY` bearer auth when configured, same 60 req/min per-client
rate limit.

Error mapping:

| Condition | HTTP | Body |
| --- | --- | --- |
| `SEARCH_THRESHOLD` unset | 503 | `{"detail": "Search is not configured"}` |
| `ModelNotFoundError` while embedding query | 503 | safe message |
| `ModelEndpointError` while embedding query | 502 | safe message |
| `QdrantStorageError` | 502 | safe message |

No raw errors, IDs beyond the matched point ID, tracebacks, or internal
paths are exposed.

### `backend/app/main.py`

- Register the new router.
- Pass `Settings` into `FileIngestionService` construction (threshold access).

## Data Flow

```
POST /v1/search
  → require_upload_access (auth + rate limit)
  → validate {"query", "limit"}
  → service.search(query, limit)
      → SettingsError? → 503
      → embed query via EMBEDDING_MODEL
      → qdrant.search(vector, limit, SEARCH_THRESHOLD)
           score >= threshold
      → map hits → public items
  → 200 {"object": "list", "data": [...]}
```

## Migration / Compatibility

- No migration. Existing points have no payload; 
  Operator deletes them manually.
- `store_embedding`'s default `payload=None` keeps current text/PDF behavior
  and all existing tests intact.

## Documentation

- README: new "Vector search" section (endpoint, request/response examples,
  threshold config, auth); configuration table gains `SEARCH_THRESHOLD`;
  privacy section rewritten (image descriptions are now persisted as Qdrant
  payload).
- `.env.example`: `SEARCH_THRESHOLD=` with comment.

## Testing (TDD)

Unit:
- `qdrant_store`: payload passed through on upsert; `search` applies
  threshold and filter (mock client); client failures raise
  `QdrantStorageError` with safe message.
- `ingestion_service`: image ingestion stores payload with filename,
  file_type, description text; text ingestion still stores no
  payload; `search` embeds query and maps hits; `search` raises when
  threshold unset; payload-less hit maps fields to `None`.
- `config`: `SEARCH_THRESHOLD` unset is allowed; values outside `[0, 1]`
  fail validation.

Integration (`TestClient`, real app wiring with fakes):
- Auth required when `UPLOAD_API_KEY` set; 401 without.
- Blank `query` / `limit` outside 1–100 → 422.
- Happy path: upload image, search, description text and filename returned,
  score >= threshold, ordered descending.
- Below-threshold results excluded.
- Threshold unset → 503 with safe detail.
- Qdrant/model failure → 502/503 safe errors.

## Risks

- Description text in payload is readable by anyone with Qdrant access —
  accepted, same trust boundary as today's vectors.
- Search response can include long descriptions; bounded by description
  pipeline output size, acceptable.
