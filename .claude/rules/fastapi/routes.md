---
paths:
  - "backend/app/api/routes/**/*.py"
  - "backend/app/api/main.py"
---
# Route Handlers

> Extends [index.md](./index.md). Load when edit `api/routes/**` or `api/main.py`.

## File Location

`backend/app/api/routes/<feature>.py` — one file per feature.

## Handler Shape

Every handler MUST declare:

- `response_model=<Public>` — never return raw ORM model
- `status_code=` — `201` POST-create, `204` DELETE, `200` GET/PATCH
- `Depends(get_db)` for DB session — see [index.md](./index.md)
- `Depends(get_current_user)` for auth — unless public
- typed Pydantic body param — never `dict` / `Any`

Handler thin: parse → call service → return. No business logic.

## Example

```python
# WRONG: fat handler, raw model, no status, no auth, no Depends
@router.post("/items/")
def create_item(payload: dict):                # plain dict — no validation
    db = SessionLocal()                        # leaks connection
    item = Item(**payload)                     # business logic in route
    db.add(item); db.commit()
    return item                                # ORM leaks internal fields
```

```python
# CORRECT: schema → service → response_model, deps + status
from fastapi import APIRouter, Depends, status
from app.api.deps import get_db, get_current_user
from app.api.schemas.items import ItemCreate, ItemPublic
from app.items import service as items_service

router = APIRouter()

@router.post(
    "/",
    response_model=ItemPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Item:
    return await items_service.create_item(db, current_user.id, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await items_service.delete_item(db, current_user.id, item_id)
```

## Register Router

Add to `backend/app/api/main.py`:

```python
from app.api.routes import items

api_router.include_router(items.router, prefix="/items", tags=["items"])
```

- `prefix` = plural noun, kebab-case if multi-word (`/data-files`)
- `tags` = OpenAPI grouping, matches prefix without slash

## After Route Change

ALWAYS run from repo root:

```bash
bash scripts/generate-client.sh
```

Regenerates frontend TypeScript client + TanStack Router tree. Skip = frontend types drift, runtime errors.

## Forbidden

- `payload: dict` / `payload: Any` — typed Pydantic schema only. See [schemas.md](./schemas.md).
- Business logic in handler — move to service. See [services.md](./services.md).
- Return ORM model without `response_model` — leaks internal fields.
- Missing `status_code` on POST/DELETE — defaults 200, semantically wrong.
- New route without test using `app.dependency_overrides`.
- Skip `scripts/generate-client.sh`.