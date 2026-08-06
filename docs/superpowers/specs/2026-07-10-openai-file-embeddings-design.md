# OpenAI File Embeddings Endpoint Design

## Summary

Build a backend-only FastAPI dependency service that accepts uploaded files, sends their extracted content to an external embedding model endpoint, stores resulting vectors in Qdrant, and returns Qdrant ids. No user interface is included.

The service supports text files, images, and PDFs for now. It stores one embedding per uploaded file.

## Goals

- Provide a file upload embedding endpoint for another project to consume.
- Support text files, images, and PDFs.
- Return one Qdrant id per uploaded file.
- Store embeddings and metadata in Qdrant.
- Keep the service simple and focused.

## Non-Goals

- No frontend or upload page.
- No OCR for scanned PDFs.
- No direct model hosting inside this service.
- No raw embedding vectors returned to the caller.
- No search endpoint in this first version.

## Architecture

The service has four main responsibilities:

1. Accept file uploads through an HTTP endpoint.
2. Validate and convert each file into model-ready input.
3. Call an external embedding model endpoint.
4. Store resulting vectors in Qdrant and return stored ids.

High-level flow:

```text
CLIENT uploads one or more files
SERVICE validates request and files
FOR EACH file:
    detect file type
    convert file into text or image input
    send converted input to external embedding model endpoint
    receive embedding vector
    create Qdrant point with vector and metadata
    store point in Qdrant
    add id to response
SERVICE returns response with per-file results
```

## Endpoint Design

### Main endpoint

`POST /v1/file-embeddings`

Request format:

```text
multipart form data containing:
    files: one or more uploaded files
    model: embedding model name
```

Rules:

```text
IF no files are provided:
    reject request with client error (e.g. "No files provided. Please attach at least one file.")

IF more than max file count are provided:
    reject request with client error

FOR EACH file:
    process independently
    store successful embedding in Qdrant
    record per-file error if processing fails
```

Response shape:

```text
FileEmbeddingResponse:
    object: list
    data: list of FileEmbeddingItem

FileEmbeddingItem:
    filename: original uploaded filename
    content_type: uploaded content type when available
    id: Qdrant id when stored successfully
    error: error message when processing failed
```

Example response shape:

```text
response object:
    object is list
    data contains:
        item with filename report.pdf, content type application/pdf, id generated UUID, no error
        item with filename photo.png, content type image/png, id generated UUID, no error
```

### Health endpoint

`GET /health`

Behavior:

```text
check service process is alive
check Qdrant is reachable
check external model endpoint is reachable
return status for each dependency
```

Response shape:

```text
HealthResponse:
    status: overall status
    qdrant: Qdrant dependency status
    model: external model endpoint status
```

### Retrieval endpoint

`GET /v1/file-embeddings/{id}`

Behavior:

```text
receive id
look up point payload in Qdrant
IF point exists:
    return stored metadata without vector
ELSE:
    return not found error
```

Response shape:

```text
StoredFileEmbeddingResponse:
    id: Qdrant id
    filename: stored filename
    content_type: stored content type
    file_type: detected file type
    model: embedding model used
    created_at: storage timestamp
```

## Pydantic Models

Use Pydantic models for response bodies and validated request configuration fields.

Multipart uploaded files are handled as FastAPI upload objects, not pure JSON request models.

Models:

```text
FileEmbeddingRequest:
    model: embedding model name

FileEmbeddingItem:
    filename: string
    content_type: string or empty
    id: string or empty
    error: string or empty

FileEmbeddingResponse:
    object: list marker
    data: list of FileEmbeddingItem

ErrorDetail:
    message: string
    type: string
    filename: string or empty

ErrorResponse:
    error: ErrorDetail

HealthResponse:
    status: string
    qdrant: string
    model: string

StoredFileEmbeddingResponse:
    id: string
    filename: string
    content_type: string
    file_type: string
    model: string
    created_at: string timestamp
```

## File Handling

Supported file groups:

```text
TEXT files:
    txt, markdown, csv, json, xml, yaml, yml, Python, JavaScript, TypeScript, HTML, CSS, and similar plain text files

IMAGE files:
    png, jpg, jpeg, webp

PDF files:
    pdf
```

Validation rules:

```text
max files per request is 10
max file size is 25 MB
empty files are rejected
unsupported file types receive per-file error
```

### File type detection

Use `python-magic` (libmagic bindings) to detect MIME type from file content:

```text
read file bytes
detect MIME type via python-magic from content bytes
map MIME type to file group:
    text/plain, text/csv, text/markdown, application/json, application/xml, text/yaml, text/html, text/css, and text/x-* → text
    image/png, image/jpeg, image/webp → image
    application/pdf → pdf
    anything else → unsupported
```

Extension is not used for detection — content-based only. A `.pdf` renamed to `.txt` still routes to PDF processing.

### Text file processing

```text
read file bytes
try to decode bytes as UTF-8
IF decode succeeds:
    create model input with text content
ELSE:
    return per-file decode error
```

### Image file processing

```text
read file bytes
try to open image with image validation library
IF image is valid:
    create model input with image bytes
ELSE:
    return per-file invalid image error
```

### PDF processing

```text
read file bytes
extract text from all PDF pages
combine page text into one text string
IF combined text is not empty:
    create model input with combined text
ELSE:
    return per-file error saying PDF has no extractable text
```

Scanned PDF handling is not included in this version. OCR can be added later if needed.

## Model Endpoint Integration

The service calls an external embedding model endpoint. The model endpoint supports both text and image inputs.

Model client responsibilities:

```text
FUNCTION embed text input:
    send text and model name to external endpoint
    receive embedding vector
    return vector

FUNCTION embed image input:
    send image bytes and model name to external endpoint
    receive embedding vector
    return vector
```

Error handling:

```text
IF external model endpoint times out:
    return per-file model timeout error

IF external model endpoint rejects input:
    return per-file model rejection error
```

Configuration:

```text
MODEL_ENDPOINT_URL comes from environment
MODEL_ENDPOINT_API_KEY comes from environment when needed
MODEL_REQUEST_TIMEOUT comes from environment or default constant
```

No secrets are hardcoded.

## Qdrant Integration

Qdrant stores vectors and metadata.

Collection:

```text
file_embeddings
```

Each successful file creates one Qdrant point.

Point ID:

```text
generate UUID per uploaded file
```

Point vector:

```text
embedding vector returned by external model endpoint
```

Point payload:

```text
filename: original uploaded filename
content_type: uploaded content type when available
file_type: detected type such as text, image, or pdf
model: model name used
created_at: current timestamp
```

Optional future payload fields:

```text
document_id
project_id
tags
```

Qdrant behavior:

```text
IF collection does not exist at startup:
    create collection using configured vector size and distance metric

WHEN file embedding succeeds:
    upsert point into collection

IF Qdrant upsert fails:
    return per-file storage error
```

Configuration:

```text
QDRANT_URL comes from environment
QDRANT_API_KEY comes from environment when needed
QDRANT_COLLECTION defaults to file_embeddings
QDRANT_VECTOR_SIZE must match embedding model output size
QDRANT_DISTANCE defaults to cosine
```

## Error Handling

Request-level errors:

```text
no files provided
invalid model field
too many files
request payload too large
```

These return HTTP client errors.

Per-file errors:

```text
unsupported file type
empty file
text decode failure
invalid image
PDF has no extractable text
model endpoint failure
Qdrant storage failure
```

These are included in the response item for that file.

All-file failure behavior:

```text
IF request itself is valid but every file fails:
    return normal response with per-file errors
```

Dependency-wide failure behavior:

```text
IF Qdrant is unavailable before processing starts:
    return service error

IF model endpoint is unavailable before processing starts:
    return bad gateway style service error
```

## Security and Validation

Security rules:

```text
never trust uploaded filename
never write uploaded files using original filename without sanitization
never hardcode API keys
limit file count
limit file size
validate file type by extension and content where possible
reject empty files
return safe error messages to client
log detailed server-side context without leaking secrets
```

No authentication is defined in this first design. If exposed beyond trusted local/internal network, add API key authentication before deployment.

## Testing Plan

Implementation should follow TDD.

Unit tests:

```text
file type detection returns text for supported text extensions
file type detection returns image for supported image extensions
file type detection returns pdf for PDF extension
file type detection rejects unsupported extension
text decode succeeds for UTF-8 file
text decode fails cleanly for invalid bytes
image validation succeeds for valid image
image validation fails for invalid image bytes
PDF extraction succeeds for text PDF
PDF extraction returns clear error for PDF with no text
response models validate success item
response models validate error item
```

Integration tests:

```text
POST file embeddings with one text file stores one Qdrant point
POST file embeddings with one image file stores one Qdrant point
POST file embeddings with one PDF file stores one Qdrant point
POST file embeddings with multiple files returns one item per file
model endpoint client receives text input for text files
model endpoint client receives image input for image files
Qdrant client receives vector and payload
GET stored point returns metadata without vector
GET missing point returns not found error
GET health reports Qdrant and model status
```

Error tests:

```text
unsupported extension returns per-file error
empty file returns per-file error
too many files returns request error
oversized file returns request error
model endpoint timeout returns per-file error
Qdrant upsert failure returns per-file error
```

External dependencies in tests:

```text
mock model endpoint
mock Qdrant client or use test Qdrant instance
```

## Open Questions Resolved

- No UI is included.
- Endpoint uses multipart file uploads, not OpenAI standard JSON embeddings format.
- Service returns Qdrant ids only, not raw embedding vectors.
- One embedding is stored per uploaded file.
- PDFs use text extraction only for first version.
- Scanned PDFs and OCR are out of scope for now.
