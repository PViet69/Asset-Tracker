---
paths:
  - "backend/app/main.py"
  - "backend/app/api/**/*.py"
---
# FastAPI Rules

> Extends [python/coding-style.md](../python/coding-style.md), [python/patterns.md](../python/patterns.md), [python/testing.md](../python/testing.md) (extend `common/*`). This file = FastAPI-specific only.

## Structure

- App construction in `create_app()`.
- Routers thin; persistence + business logic in services/CRUD helpers.
- Request, update, response schemas separate.
- DB sessions + auth in dependencies.

## Async

- `async def` for I/O endpoints.
- Async DB + HTTP clients from async endpoints.
- No `requests`, sync SQLAlchemy, or blocking I/O from async routes.

### No sync/async bridging hacks

No bridging async↔sync via `asyncio.run` in worker thread, nested loops, `loop.run_until_complete` on running loop, similar tricks. Hide blocking calls, break cancellation, leak threads.

Sync caller needs async leaf (or reverse), pick one:

1. **Use sync sibling.** Most Google Cloud, gRPC, HTTP libs ship both — match call site.
2. **Make caller match.** Convert sync chain to `async def` (or async chain to `def`); pick longer-reach side. Use `def` endpoint when work mostly sync — FastAPI runs in threadpool.
3. **Offload sync chain.** From async caller, wrap sync block with `await asyncio.to_thread(fn, ...)` or `await anyio.to_thread.run_sync(fn, ...)`. Standard, cancellable, no manual threads.

Hand-rolled `threading.Thread(target=lambda: asyncio.run(coro))` = smell. Boundary in wrong place.

## Dependency Injection

```python
# WRONG: SessionLocal inside handler — leaks connections, untestable
@router.get("/users/{user_id}")
async def get_user(user_id: str):
    db = SessionLocal()
    user = db.query(User).filter_by(id=user_id).first()
    return user  # session never closed, no test override

# CORRECT: Depends — lifecycle managed, override-able in tests
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ...
```

No `SessionLocal()` or long-lived clients inside route handlers.

## Schemas

- Never include passwords, hashes, access/refresh tokens, internal auth state in response models.
- Use `response_model` on endpoints returning app data.
- Field constraints over hand-written validation when Pydantic expresses rule.

## Security

- CORS origins environment-specific.
- No wildcard origins + credentialed CORS.
- Validate JWT expiry, issuer, audience, algorithm.
- Rate-limit auth + write-heavy endpoints.
- Redact credentials, cookies, auth headers, tokens from logs.

## Testing

- Override exact dependency used by `Depends`.
- Clear `app.dependency_overrides` after tests.
- Prefer async test clients for async apps.