# Embedding Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TypeScript SPA at `frontend/` that talks to the existing FastAPI embedding backend via three surfaces: Upload, Search, and a header-mounted Health badge.

**Architecture:** Vite + React 18 + TypeScript (strict mode). Single page with two-tab segmented control. Hand-written `fetch` wrappers with typed response shapes. Hand-written CSS implementing the dark glassmorphism design from `frontend-mockup.html`. No UI framework, no state lib, no router. Vite dev-server proxies `/v1` and `/health` to the backend on `localhost:8000` so dev works without CORS changes.

**Tech Stack:** Vite 5, React 18, TypeScript 5 (strict), zero runtime deps beyond React. Dev deps: `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`.

**Spec:** `docs/superpowers/specs/2026-08-19-embedding-frontend-design.md`
**Mockup:** `frontend-mockup.html` (visual reference — copy design tokens, not markup)

## Spec Corrections (backend is source of truth)

The spec's `types.ts` snippet has field-name drift vs the real Pydantic schemas. Plan uses the actual shapes:

- `FileEmbeddingItem.status` is `"success" | "failed"` (not `stored|skipped|error`). Mockup's "stored/skipped" labels are visual only — UI maps `success→stored`, `failed→error`, and renders `reason` when present.
- `FileEmbeddingItem` has `content_type: str = ""` (default).
- `FileEmbeddingResponse` wraps with `object: "list"` and `data: FileEmbeddingItem[]` (the spec snippet omits `object` — keep it in TS).
- `VectorSearchItem` fields: `point_id, score, filename, file_path, file_type, content` (not `id/description`). UI shows `filename` + rounded `score` + `content` as snippet.
- `VectorSearchRequest.limit` defaults to `10` (spec says `5` in JS). Use backend default `10`, allow 1–100.
- `HealthResponse` is flat `{ status, qdrant, model }` — no nested `description`/`model.status`. UI maps `status==="ok"` to green, anything else (incl. `"degraded"`) to amber.

## Global Constraints

- TypeScript `strict: true`, `noUncheckedIndexedAccess: true`.
- React 18, no Suspense, no concurrent features, no react-router.
- Vite dev port `5173`; API base in dev = `/` (proxied to `http://localhost:8000`).
- Production build: API base from `import.meta.env.VITE_API_BASE` defaulting to `http://localhost:8000`.
- API key (optional bearer) read once from `VITE_API_KEY` at module load; never logged, never surfaced in UI.
- `.env.local` git-ignored; `.env.example` ships placeholders only.
- `.gitignore` adds `frontend/node_modules/`, `frontend/dist/`, `frontend/.env.local`.
- Visual: dark glassmorphism, accent `#a78bff`, accent-2 `#5fa8ff`, OK `#4ade80`, WARN `#fbbf24`, ERR `#fb7185`. Honor `prefers-reduced-motion`.
- Hard refresh requirement: `npm run build` MUST succeed (tsc strict + Vite prod bundle).
- No unit tests in this scope (per spec). Backend integration tests cover the API.

## File Structure (target)

```
frontend/
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── index.html
├── .env.example
├── .gitignore                  # if not in repo .gitignore
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── config.ts
    ├── types.ts
    ├── api/
    │   └── client.ts
    ├── components/
    │   ├── HealthBadge.tsx
    │   ├── UploadPanel.tsx
    │   └── SearchPanel.tsx
    └── styles.css
```

Plus repo-root `.gitignore` additions and a `frontend/.gitignore` for `node_modules/`.

---

### Task 1: Scaffold Vite + React + TS project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`
- Create: `frontend/.env.example`
- Modify: `/Users/narutojaki/GravityGlobal/Asset-Tracker/.gitignore`

**Interfaces:**
- Consumes: nothing (greenfield)
- Produces: installable Vite project; `npm run dev` boots, `npm run build` succeeds on an empty `<App/>` that renders `<h1>Embedding UI</h1>`.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "embedding-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc -b --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }
}
```

- [ ] **Step 2: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowImportingTsExtensions": false,
    "verbatimModuleSyntax": true,
    "useDefineForClassFields": true,
    "noEmit": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Write `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Write `frontend/vite.config.ts`**

```ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_API_BASE ?? "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/v1": { target: apiBase, changeOrigin: true },
        "/health": { target: apiBase, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
```

- [ ] **Step 5: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Embedding UI</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Write `frontend/.gitignore`**

```
node_modules/
dist/
.env.local
.env.*.local
*.log
.DS_Store
```

- [ ] **Step 7: Write `frontend/.env.example`**

```
# Backend root URL. Override per-developer in `.env.local`.
VITE_API_BASE=http://localhost:8000

# Optional bearer token sent as `Authorization: Bearer <key>`.
# Leave unset for local dev against an unauthenticated backend.
VITE_API_KEY=
```

- [ ] **Step 8: Update repo-root `.gitignore`**

Append to `/Users/narutojaki/GravityGlobal/Asset-Tracker/.gitignore`:

```
# Frontend
frontend/node_modules/
frontend/dist/
frontend/.env.local
```

- [ ] **Step 9: Write minimal `frontend/src/main.tsx` + `App.tsx` to enable first build**

`frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");
ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`frontend/src/App.tsx`:

```tsx
export function App(): JSX.Element {
  return <h1>Embedding UI</h1>;
}
```

- [ ] **Step 10: Install + verify build**

```bash
cd frontend && npm install && npm run build
```

Expected: `dist/` produced, exit 0, no TS errors.

- [ ] **Step 11: Verify dev server boots**

```bash
cd frontend && npm run dev
```

Expected: `Local: http://localhost:5173/` printed, page renders "Embedding UI" in browser.

- [ ] **Step 12: Commit**

```bash
git add frontend/.gitignore frontend/.env.example frontend/.gitignore frontend/index.html frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/src/main.tsx frontend/src/App.tsx .gitignore
git commit -m "feat(frontend): scaffold vite + react + ts with proxy to backend"
```

---

### Task 2: Config + types module

**Files:**
- Create: `frontend/src/config.ts`
- Create: `frontend/src/types.ts`

**Interfaces:**
- Consumes: Vite env vars (`import.meta.env`)
- Produces:
  - `config: Readonly<{ apiBase: string; apiKey?: string }>`
  - Types: `FileStatus`, `FileEmbeddingItem`, `FileEmbeddingResponse`, `VectorSearchItem`, `VectorSearchResponse`, `HealthResponse`, `ApiError` (later task)

- [ ] **Step 1: Write `frontend/src/config.ts`**

```ts
type AppConfig = {
  readonly apiBase: string;
  readonly apiKey?: string;
};

function readEnv(key: string): string | undefined {
  const value = import.meta.env[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export const config: AppConfig = Object.freeze({
  apiBase: readEnv("VITE_API_BASE") ?? "http://localhost:8000",
  apiKey: readEnv("VITE_API_KEY"),
});
```

- [ ] **Step 2: Write `frontend/src/types.ts`**

```ts
// Mirrors backend/app/api/schemas/file_embeddings.py
export type FileStatus = "success" | "failed";

export type FileEmbeddingItem = {
  filename: string;
  content_type: string;
  status: FileStatus;
  reason: string | null;
};

export type FileEmbeddingResponse = {
  object: "list";
  data: FileEmbeddingItem[];
};

// Mirrors backend/app/api/schemas/vector_search.py
export type VectorSearchItem = {
  point_id: string;
  score: number;
  filename: string;
  file_path: string;
  file_type: string;
  content: string;
};

export type VectorSearchResponse = {
  object: "list";
  data: VectorSearchItem[];
};

// Mirrors backend/app/api/schemas/health.py
export type HealthResponse = {
  status: string; // "ok" | "degraded" | ...
  qdrant: string;
  model: string;
};

export type ApiError = {
  status: number;
  message: string;
};
```

- [ ] **Step 3: Verify typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0, no diagnostics.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config.ts frontend/src/types.ts
git commit -m "feat(frontend): add config and backend-mirror types"
```

---

### Task 3: API client (`fetch` wrappers + typed errors)

**Files:**
- Create: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: `config` from `./config`, types from `./types`
- Produces:
  - `class ApiError implements ApiError { constructor(status, message); status: number; message: string }`
  - `uploadFiles(files: File[], onProgress?: undefined): Promise<FileEmbeddingResponse>`
  - `searchVectors(query: string, limit?: number): Promise<VectorSearchResponse>`
  - `checkHealth(): Promise<HealthResponse>`

- [ ] **Step 1: Write `frontend/src/api/client.ts`**

```ts
import { config } from "../config";
import type {
  ApiError,
  FileEmbeddingResponse,
  HealthResponse,
  VectorSearchResponse,
} from "../types";

export class ApiError extends Error implements ApiError {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function buildHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  if (config.apiKey !== undefined && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${config.apiKey}`);
  }
  return headers;
}

async function parseError(res: Response): Promise<never> {
  // FastAPI returns { detail: string | { msg: ... } } on errors.
  // Backend exceptions already produce sanitized safe_message strings.
  let message = `Request failed with status ${res.status}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.length > 0) {
      message = body.detail;
    } else if (body.detail && typeof body.detail === "object") {
      message = JSON.stringify(body.detail);
    }
  } catch {
    // body wasn't JSON — keep status-based message
  }
  throw new ApiError(res.status, message);
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${config.apiBase}${path}`, {
    method: "GET",
    headers: buildHeaders(),
  });
  if (!res.ok) await parseError(res);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${config.apiBase}${path}`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) await parseError(res);
  return (await res.json()) as T;
}

export function checkHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function searchVectors(
  query: string,
  limit: number = 10
): Promise<VectorSearchResponse> {
  return postJson<VectorSearchResponse>("/v1/search", { query, limit });
}

export async function uploadFiles(
  files: File[]
): Promise<FileEmbeddingResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  // NOTE: do NOT set Content-Type — browser must add the multipart boundary.
  const res = await fetch(`${config.apiBase}/v1/file-embeddings`, {
    method: "POST",
    headers: buildHeaders(),
    body: form,
  });
  if (!res.ok) await parseError(res);
  return (await res.json()) as FileEmbeddingResponse;
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): add typed api client with fetch wrappers"
```

---

### Task 4: Global styles (glassmorphism design tokens)

**Files:**
- Create: `frontend/src/styles.css`

**Interfaces:**
- Consumes: nothing
- Produces: design tokens + components matching `frontend-mockup.html`. CSS classes used by components in later tasks: `.app`, `.glass`, `.bar`, `.brand`, `.logo`, `.pill`, `.pill.ok/warn/err`, `.tabs`, `.tab`, `.panel-card`, `.field`, `.input`, `.drop`, `.actions`, `.primary`, `.results`, `.list`, `.row-line`, `.fname`, `.meta-row`, `.snippet`, `.badge`, `.badge.stored/skipped/error`, `.score`, `.banner`.

- [ ] **Step 1: Write `frontend/src/styles.css`**

Copy the contents of `/Users/narutojaki/GravityGlobal/Asset-Tracker/frontend-mockup.html` lines 8–300 (everything inside `<style>...</style>`) into `frontend/src/styles.css` verbatim. Adjustments vs. mockup:
  - Add `body { padding: 0; }` already covered.
  - Change `font: 14px/1.55 -apple-system, ...` to include "Inter" first: `font: 14px/1.55 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;`.
  - The `.drop` block has hover/active state defined in the mockup; keep it.
  - Keep `prefers-reduced-motion` media query at the end.

- [ ] **Step 2: Mount stylesheet**

In `frontend/src/main.tsx`, prepend:

```ts
import "./styles.css";
```

So the final file is:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");
ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 3: Verify build still passes**

```bash
cd frontend && npm run build
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles.css frontend/src/main.tsx
git commit -m "feat(frontend): port glassmorphism design tokens from mockup"
```

---

### Task 5: `HealthBadge` component

**Files:**
- Create: `frontend/src/components/HealthBadge.tsx`

**Interfaces:**
- Consumes: `checkHealth()` from `../api/client`
- Produces: `<HealthBadge/>` React component. Props: none. State: `state: "idle" | "ok" | "degraded" | "err"`.

- [ ] **Step 1: Write `frontend/src/components/HealthBadge.tsx`**

```tsx
import { useEffect, useState } from "react";
import { checkHealth } from "../api/client";

type BadgeState = "idle" | "ok" | "degraded" | "err";

function pillClass(state: BadgeState): string {
  if (state === "idle") return "pill";
  return `pill show ${state}`;
}

function pillText(state: BadgeState): string {
  switch (state) {
    case "ok":
      return "ok";
    case "degraded":
      return "degraded";
    case "err":
      return "unreachable";
    case "idle":
      return "";
  }
}

export function HealthBadge(): JSX.Element {
  const [state, setState] = useState<BadgeState>("idle");

  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then((res) => {
        if (cancelled) return;
        setState(res.status === "ok" ? "ok" : "degraded");
      })
      .catch(() => {
        if (cancelled) return;
        setState("err");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <span className={pillClass(state)} aria-live="polite">
      <span className="dot" />
      <span>{pillText(state)}</span>
    </span>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/HealthBadge.tsx
git commit -m "feat(frontend): add HealthBadge with mounted fetch"
```

---

### Task 6: `UploadPanel` component

**Files:**
- Create: `frontend/src/components/UploadPanel.tsx`

**Interfaces:**
- Consumes: `uploadFiles()` from `../api/client`, types `FileEmbeddingResponse`, `FileEmbeddingItem`
- Produces: `<UploadPanel/>` React component. Props: none. Behavior: `<input type="file" multiple>` (no API key field), build FormData, render results list with status badge + reason. Errors render a banner.

- [ ] **Step 1: Write `frontend/src/components/UploadPanel.tsx`**

```tsx
import { useRef, useState, type ChangeEvent } from "react";
import { ApiError, uploadFiles } from "../api/client";
import type { FileEmbeddingItem } from "../types";

type UploadState =
  | { kind: "idle" }
  | { kind: "submitting"; files: File[] }
  | { kind: "result"; items: FileEmbeddingItem[] }
  | { kind: "error"; message: string };

function badgeClassFor(status: FileEmbeddingItem["status"]): string {
  return status === "success" ? "badge stored" : "badge error";
}

function badgeLabel(status: FileEmbeddingItem["status"]): string {
  return status === "success" ? "stored" : "failed";
}

export function UploadPanel(): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [state, setState] = useState<UploadState>({ kind: "idle" });
  const [pending, setPending] = useState<File[]>([]);

  function onPick(event: ChangeEvent<HTMLInputElement>): void {
    const files = event.target.files ? Array.from(event.target.files) : [];
    setPending(files);
  }

  function openPicker(): void {
    inputRef.current?.click();
  }

  async function onSubmit(): Promise<void> {
    if (pending.length === 0) return;
    setState({ kind: "submitting", files: pending });
    try {
      const res = await uploadFiles(pending);
      setState({ kind: "result", items: res.data });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Upload failed";
      setState({ kind: "error", message });
    }
  }

  return (
    <section className="glass panel-card" role="tabpanel">
      <input
        ref={inputRef}
        type="file"
        multiple
        onChange={onPick}
        style={{ display: "none" }}
        accept=".pdf,.txt,.md,.png,.jpg,.jpeg,application/pdf,text/plain,text/markdown,image/png,image/jpeg"
      />

      <button
        type="button"
        className="drop"
        onClick={openPicker}
        aria-label="Choose files"
      >
        <strong>Click to browse</strong> or drop files here
        <div className="meta">PDF, TXT, MD, PNG, JPG · up to 10 files</div>
      </button>

      <div className="actions">
        <span className="meta">
          {pending.length} file{pending.length === 1 ? "" : "s"} selected
        </span>
        <button
          className="primary"
          type="button"
          onClick={onSubmit}
          disabled={state.kind === "submitting" || pending.length === 0}
        >
          Upload &amp; embed
        </button>
      </div>

      {state.kind === "error" && (
        <div className="banner" role="alert">
          {state.message}
        </div>
      )}

      {state.kind === "result" && (
        <div className="results">
          <h3>Results</h3>
          <ul className="list">
            {state.items.map((item) => (
              <li key={item.filename + (item.reason ?? "")}>
                <div className="row-line">
                  <span className="fname">{item.filename}</span>
                  <span className={badgeClassFor(item.status)}>
                    {badgeLabel(item.status)}
                  </span>
                </div>
                <div className="meta-row">
                  {item.content_type}
                  {item.reason ? ` · ${item.reason}` : ""}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/UploadPanel.tsx
git commit -m "feat(frontend): add UploadPanel with file picker + results list"
```

---

### Task 7: `SearchPanel` component

**Files:**
- Create: `frontend/src/components/SearchPanel.tsx`

**Interfaces:**
- Consumes: `searchVectors()` from `../api/client`, types `VectorSearchResponse`, `VectorSearchItem`
- Produces: `<SearchPanel/>` React component. Props: none. Behavior: query input + top-k input (default 10, 1–100). Submit → `searchVectors`. Render hits: filename, score (3dp), `content` snippet.

- [ ] **Step 1: Write `frontend/src/components/SearchPanel.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { ApiError, searchVectors } from "../api/client";
import type { VectorSearchItem } from "../types";

const DEFAULT_TOP_K = 10;
const MIN_TOP_K = 1;
const MAX_TOP_K = 100;

type SearchState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "result"; items: VectorSearchItem[] }
  | { kind: "error"; message: string };

function formatScore(score: number): string {
  return score.toFixed(3);
}

export function SearchPanel(): JSX.Element {
  const [query, setQuery] = useState<string>("");
  const [topK, setTopK] = useState<number>(DEFAULT_TOP_K);
  const [state, setState] = useState<SearchState>({ kind: "idle" });

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length === 0) return;
    const clamped = Math.max(
      MIN_TOP_K,
      Math.min(MAX_TOP_K, Number.isFinite(topK) ? topK : DEFAULT_TOP_K)
    );
    setState({ kind: "submitting" });
    try {
      const res = await searchVectors(trimmed, clamped);
      setState({ kind: "result", items: res.data });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Search failed";
      setState({ kind: "error", message });
    }
  }

  return (
    <section className="glass panel-card" role="tabpanel">
      <form onSubmit={onSubmit}>
        <div className="grid-2">
          <div>
            <label className="field" htmlFor="search-q">
              Query
            </label>
            <div className="input">
              <input
                id="search-q"
                type="text"
                placeholder="describe what you're looking for"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="field" htmlFor="search-k">
              Top K
            </label>
            <div className="input">
              <input
                id="search-k"
                type="number"
                min={MIN_TOP_K}
                max={MAX_TOP_K}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              />
            </div>
          </div>
        </div>

        <div className="actions" style={{ justifyContent: "flex-end" }}>
          <button
            className="primary"
            type="submit"
            disabled={state.kind === "submitting" || query.trim().length === 0}
          >
            Search
          </button>
        </div>
      </form>

      {state.kind === "error" && (
        <div className="banner" role="alert">
          {state.message}
        </div>
      )}

      {state.kind === "result" && (
        <div className="results">
          <h3>Hits</h3>
          <ul className="list">
            {state.items.map((item) => (
              <li key={item.point_id}>
                <div className="row-line">
                  <span className="fname">{item.filename}</span>
                  <span className="score">{formatScore(item.score)}</span>
                </div>
                <div className="snippet">{item.content}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Verify typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SearchPanel.tsx
git commit -m "feat(frontend): add SearchPanel with query + topK"
```

---

### Task 8: `App` shell with tab strip

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `HealthBadge`, `UploadPanel`, `SearchPanel`
- Produces: header (brand + `HealthBadge`), segmented tab control (Upload | Search), active panel rendered below. Local `useState` for active tab.

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { useState } from "react";
import { HealthBadge } from "./components/HealthBadge";
import { UploadPanel } from "./components/UploadPanel";
import { SearchPanel } from "./components/SearchPanel";

type Tab = "upload" | "search";

export function App(): JSX.Element {
  const [tab, setTab] = useState<Tab>("upload");

  return (
    <div className="app">
      <header className="bar">
        <div className="brand">
          <div className="logo" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="#0a0d14"
              strokeWidth={2.4}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2L3 7l9 5 9-5-9-5z" />
              <path d="M3 12l9 5 9-5" />
              <path d="M3 17l9 5 9-5" />
            </svg>
          </div>
          <div>
            <h1>Embedding UI</h1>
            <div className="sub">OpenAI-compatible · quick tester</div>
          </div>
        </div>
        <HealthBadge />
      </header>

      <div className="tabs" role="tablist">
        <button
          className="tab"
          role="tab"
          aria-selected={tab === "upload"}
          onClick={() => setTab("upload")}
          type="button"
        >
          Upload
        </button>
        <button
          className="tab"
          role="tab"
          aria-selected={tab === "search"}
          onClick={() => setTab("search")}
          type="button"
        >
          Search
        </button>
      </div>

      {tab === "upload" ? <UploadPanel /> : <SearchPanel />}
    </div>
  );
}
```

- [ ] **Step 2: Verify build + typecheck**

```bash
cd frontend && npm run build
```

Expected: exit 0, `dist/` produced, no TS errors.

- [ ] **Step 3: Manual smoke check against running backend**

```bash
# Terminal 1 — backend
cd /Users/narutojaki/GravityGlobal/Asset-Tracker && uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open `http://localhost:5173/`. Verify:
  1. HealthBadge pill renders "ok" (green) within ~1s.
  2. Upload tab: click drop zone, select a `.txt` file, click "Upload & embed", result list shows `stored`.
  3. Search tab: type a query, click "Search", hits render with 3-dp score.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): wire App shell with tab strip and panels"
```

---

### Task 9: README + verification

**Files:**
- Modify: `/Users/narutojaki/GravityGlobal/Asset-Tracker/README.md` (add a "Frontend" section)

**Interfaces:**
- Consumes: nothing
- Produces: documented run instructions for the frontend.

- [ ] **Step 1: Append a Frontend section to `README.md`**

Add at end of file (find existing section headings and append a new top-level section):

```markdown
## Frontend (Embedding UI)

A small Vite + React + TypeScript SPA at `frontend/` for uploading files and searching vectors against the running FastAPI backend.

### Setup

```bash
cd frontend
npm install
cp .env.example .env.local   # optional — adjust VITE_API_BASE / VITE_API_KEY
```

### Run (dev)

```bash
# Terminal 1: backend on :8000
uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: frontend on :5173 (proxies /v1 + /health to :8000)
cd frontend && npm run dev
```

Open `http://localhost:5173/`.

### Build

```bash
cd frontend && npm run build   # tsc -b + vite build, output in frontend/dist
```

### Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE` | `http://localhost:8000` | Backend root URL. In dev, only used for the Vite proxy target; production builds hit it directly. |
| `VITE_API_KEY`  | unset                | Optional bearer token sent as `Authorization: Bearer <key>`. Never surfaced in UI. |
```

- [ ] **Step 2: Final verification**

```bash
cd /Users/narutojaki/GravityGlobal/Asset-Tracker
git status            # confirm only frontend/ + .gitignore + README.md changed
cd frontend && npm run build && npm run typecheck
```

Expected: clean status, exit 0 on both checks.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add frontend run instructions to README"
```

---

## Self-Review Notes

**Spec coverage check:**
- Configuration block (`config.ts`, `.env.example`, `.gitignore`) → Tasks 1, 2.
- Visual direction (dark, glassmorphism, tokens, reduced-motion) → Task 4 (CSS port from mockup).
- Three API wrappers + ApiError → Task 3.
- HealthBadge → Task 5.
- UploadPanel (no key field, file picker, FormData, results list, error banner) → Task 6.
- SearchPanel (query + top-k, results list) → Task 7.
- App shell (header + tabs + active panel) → Task 8.
- Error handling (banner from `error.message`, no console logging of keys) → Tasks 5–7 (no `console.error` of `ApiError`, ApiError doesn't carry the key).
- Testing (`npm run build` + `npm run dev`) → Tasks 1, 8.
- Out-of-scope (auth, queue, vector store browser) → not addressed (correct).
- README/docs → Task 9.

**Placeholder scan:** No "TODO", "TBD", "appropriate error handling", or "similar to Task N". Every code step has the actual code.

**Type consistency:**
- `FileStatus`, `FileEmbeddingItem`, `FileEmbeddingResponse`, `VectorSearchItem`, `VectorSearchResponse`, `HealthResponse`, `ApiError` defined in Task 2 and used verbatim in Tasks 3, 6, 7.
- `ApiError` declared as both `class` and `type` (TS allows class-as-type via implements). `client.ts` exports `class ApiError`. `types.ts` declares the structural type used by `implements`.
- `checkHealth()`, `searchVectors()`, `uploadFiles()` exported by Task 3, imported in Tasks 5/6/7.
- `config` exported by Task 2, used by Task 3 only — components never import it directly (matches spec).

**Spec→backend drift noted:** See "Spec Corrections" block at top. Plan reflects actual Pydantic shapes; spec snippet in `types.ts` section was misleading on `stored|skipped|error` status names and on `description` field. Plan documents the corrections inline.