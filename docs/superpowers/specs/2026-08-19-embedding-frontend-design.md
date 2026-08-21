# Embedding Frontend — Design

Date: 2026-08-19
Status: Draft
Branch: feat/embedding-frontend

## Summary

Add a small TypeScript SPA at `frontend/` that talks to the existing FastAPI
embedding backend. Three surfaces, one tab each (Upload, Search) plus a
header-mounted health badge. No backend changes.

## Goals

- Drive `POST /v1/file-embeddings`, `POST /v1/search`, and `GET /health`
  from a single-page React UI without any new backend endpoints.
- Match backend response shapes via TypeScript types — no SDK, just typed
  `fetch` wrappers.
- Stay under one afternoon of work: Vite + React + TS, no UI framework,
  no state library, no routing library.

## Non-Goals

- Auth flow beyond a per-request API key field (no session storage, no
  login screen).
- Image previews, vector visualization, search history, persisted results.
- Server-side rendering, Next.js features, or any SSR proxy.
- Unit tests (backend already has integration coverage; build covers types).

## Configuration

All secrets and URLs live in `frontend/src/config.ts` — never exposed in
the UI. No API key field, no API base field on any panel.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE` | No | `http://localhost:8000` | Backend root URL. |
| `VITE_API_KEY`  | No  | `undefined`           | Optional bearer token sent on every request. |

`.env.local` is git-ignored. `.env.example` ships with placeholders and
no real values. `config.ts` exports a frozen object read once at module
load:

```ts
export const config = Object.freeze({
  apiBase: import.meta.env.VITE_API_BASE ?? "http://localhost:8000",
  apiKey:  import.meta.env.VITE_API_KEY,
});
```

The client reads `config.apiBase` + `config.apiKey` directly. Users who
need a different key run a local dev server with their own env vars — the
running app is theirs, not a multi-tenant surface.

## Architecture

```
frontend/
├── package.json
├── vite.config.ts          # Vite + React plugin
├── tsconfig.json           # strict mode
├── tsconfig.node.json
├── index.html              # mounts #root
├── .env.example            # VITE_API_BASE
├── src/
│   ├── main.tsx            # ReactDOM.createRoot
│   ├── App.tsx             # layout: header(HealthBadge) + tabs
│   ├── api/
│   │   └── client.ts       # fetch wrappers + response type guards
│   ├── types.ts            # FileEmbeddingResponse, VectorSearchResponse, HealthResponse
│   ├── components/
│   │   ├── HealthBadge.tsx
│   │   ├── UploadPanel.tsx
│   │   └── SearchPanel.tsx
│   └── styles.css          # glassmorphism, dark, hand-written
```

## Visual Direction

- **Theme:** dark with animated mesh-gradient backdrop (three radial glows,
  slow `drift` keyframe, grid mask overlay).
- **Surface:** `.glass` panels — `rgba(255,255,255,0.06)` fill, 22px
  `backdrop-filter: blur` + 160% saturate, 1px translucent border, inset
  highlight, deep drop shadow.
- **Type:** system sans (Inter fallback), uppercase micro-headers
  (`0.08em` tracking), tabular numerals on scores.
- **Tabs:** segmented control — pill background, active tab gets
  `rgba(255,255,255,0.10)` fill + inset highlight (Vercel/Linear-style).
- **Inputs:** dark inset (`rgba(0,0,0,0.25)`), focus ring uses accent
  violet with 18% halo.
- **Primary button:** gradient `accent → accent-2`, inner highlight, soft
  drop shadow; hover translates Y by 1px and brightens.
- **Drop zone:** dashed border, radial highlight at top, hover lifts 1px
  and recolors border to accent.
- **Status badges:** translucent fills + matching borders (ok/warn/err).
- **Reduced motion:** backdrop animation disabled via
  `prefers-reduced-motion`.

## Components

### `api/client.ts`

Three exported functions, all reading base URL + bearer token from
`config`:

- `uploadFiles(files: File[]): Promise<FileEmbeddingResponse>`
  — `POST {config.apiBase}/v1/file-embeddings` as `multipart/form-data`.
  Sends `Authorization: Bearer <config.apiKey>` if a key is configured.
- `searchVectors(query: string, topK?: number): Promise<VectorSearchResponse>`
  — `POST {config.apiBase}/v1/search` JSON body. Defaults `top_k=5`.
- `checkHealth(): Promise<HealthResponse>` — `GET {config.apiBase}/health`.

All three throw on non-2xx with a typed `ApiError` carrying `status` and
a safe `message` (the backend already returns sanitized errors).

### `types.ts`

Mirrors the backend Pydantic schemas verbatim:

```ts
type FileStatus = "stored" | "skipped" | "error";
type FileEmbeddingItem = {
  filename: string;
  content_type: string;
  status: FileStatus;
  reason?: string;
};
type FileEmbeddingResponse = { data: FileEmbeddingItem[] };

type VectorSearchHit = {
  id: string;
  score: number;
  filename?: string;
  content_type?: string;
  description?: string;
};
type VectorSearchResponse = { data: VectorSearchHit[] };

type HealthResponse = {
  status: "ok" | "degraded";
  description: { status: string };
  model: { status: string };
  qdrant: { status: string };
};
```

### `HealthBadge.tsx`

- Calls `checkHealth()` once on mount (`useEffect`).
- Hidden until the first response arrives; then renders colored pill:
  green `ok`, amber `degraded`, red on throw.

### `UploadPanel.tsx`

- `<input type="file" multiple>` only — no API key field.
- On submit: build `FormData`, append each file, call `uploadFiles`.
- Render response `data[]` as a list: filename, status badge, optional
  reason. Errors render as a single banner.

### `SearchPanel.tsx`

- Query input + top-k input (default 5). No API key field.
- Submit → `searchVectors`. Render hits as a list: filename, score
  (rounded to 3 dp), description snippet.

### `App.tsx`

- Header: title + `HealthBadge`.
- Tab strip: Upload | Search (local `useState`, no router).

## Error Handling

- Network error or non-2xx → render banner with `error.message`. No
  retries. No console logging of API keys.
- Health endpoint throw → badge shows red "unreachable"; upload/search
  panels still work.

## Testing

- `npm run build` (Vite production build) — must succeed, which typechecks
  via `tsc`.
- `npm run dev` — manual smoke check against a running backend.

No unit tests in this scope.

## Out-of-Scope Follow-ups

- Auth: real session/key management.
- File queue / progress bars for large uploads.
- Vector store browser (list collections, point counts).
