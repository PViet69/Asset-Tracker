---
paths:
  - "backend/app/*/service.py"
  - "backend/app/*/services.py"
  - "backend/app/*/crud.py"
  - "backend/app/*/services/**/*.py"
---
# Service Layer

> Extends [index.md](./index.md). Loads when editing `app/<feature>/service.py`, `services/**`, or `crud.py`.

## Rule

Business logic lives in `app/<feature>/service.py` (or `crud.py` for thin persistence wrappers). Route handlers never touch:

- ORM queries directly
- multi-step transactional logic
- external service calls (BigQuery, S3, third-party APIs)
- domain validation beyond Pydantic field constraints

Service functions take `AsyncSession` + typed input schema, return ORM model or domain object. FastAPI `response_model` serializes ORM → Public schema at route layer.

## File Layout

```
app/<feature>/
├── __init__.py
├── models.py        # SQLModel / SQLAlchemy ORM
├── service.py       # business logic — orchestrates crud + external calls
└── crud.py          # thin DB ops: get_by_id, list, create, update, delete
```

`crud.py` optional for simple features — fold into `service.py` when only 1–2 ops.

## Signature Pattern

```python
async def <verb>_<entity>(
    db: AsyncSession,
    <caller_context>: <Type>,        # e.g. owner_id, current_user
    <input>: <Schema>,               # Pydantic input schema, not dict
) -> <Model>:
    ...
```

## Example

```python
# WRONG: business logic in route, plain dict, no transaction boundary
@router.post("/items/")
async def create_item(payload: dict, db: AsyncSession = Depends(get_db)):
    if not payload.get("name"):
        raise HTTPException(422, "name required")
    item = Item(name=payload["name"], price=payload["price"])
    db.add(item)
    await db.commit()
    await audit_log_external(item.id)        # external call leaks into route
    return item
```

```python
# CORRECT: thin route → typed service
# app/items/service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.schemas.items import ItemCreate
from app.items.models import Item
from app.items import crud
from app.audit import audit_log

async def create_item(
    db: AsyncSession,
    owner_id: int,
    data: ItemCreate,
) -> Item:
    item = await crud.create(db, owner_id=owner_id, data=data)
    await audit_log(db, action="item.create", entity_id=item.id)
    await db.commit()
    return item

# app/items/crud.py
async def create(
    db: AsyncSession,
    *,
    owner_id: int,
    data: ItemCreate,
) -> Item:
    item = Item(**data.model_dump(), owner_id=owner_id)
    db.add(item)
    await db.flush()
    return item
```

Notes:

- `crud.create` uses `db.flush()` — caller (`service`) owns `commit()` so multi crud ops compose in one transaction.
- `service.create_item` owns commit + side effects (audit log).
- Route handler stays one line: `return await items_service.create_item(...)`.

## Errors

Raise domain exceptions in service, map to HTTP in route (or global exception handler).

```python
# WRONG: HTTPException from service — couples to FastAPI, untestable outside HTTP
async def get_item(db, item_id):
    item = await crud.get_by_id(db, item_id)
    if not item:
        raise HTTPException(404, "not found")   # service knows HTTP
    return item

# CORRECT: domain exception, route maps to HTTP
# app/items/exceptions.py
class ItemNotFound(Exception): ...

# service.py
async def get_item(db, item_id) -> Item:
    item = await crud.get_by_id(db, item_id)
    if not item:
        raise ItemNotFound(item_id)
    return item

# api/routes/items.py — handler or global exception_handler maps to 404
@app.exception_handler(ItemNotFound)
async def _not_found(_req, exc: ItemNotFound):
    return JSONResponse(status_code=404, content={"detail": f"item {exc.args[0]} not found"})
```

## Forbidden

- Import from `fastapi` in `service.py` / `crud.py` — service stay HTTP-agnostic.
- `dict[str, X]` as service input — use Pydantic input schema or `TypedDict`. See [python/patterns.md](../python/patterns.md).
- `db.commit()` inside `crud.py` — caller owns transaction boundary.
- Raw SQL strings — use SQLAlchemy core/ORM or parameterized `text()`.

## Related

- Route layer: [routes.md](./routes.md)
- Schema layer: [schemas.md](./schemas.md)
- Migrations when models change: [database-migrations.md](../database-migrations.md)