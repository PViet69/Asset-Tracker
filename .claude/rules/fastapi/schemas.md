---
paths:
  - "backend/app/api/schemas/**/*.py"
---
# API Schemas

> Extends [index.md](./index.md). Loads when editing `api/schemas/**`.

## Rule

Every endpoint = 3 Pydantic schemas per resource:

- `<Feature>Create` — POST body (required fields only)
- `<Feature>Update` — PATCH/PUT body (all optional)
- `<Feature>Public` — response shape (no secrets, no internal cols)

Never reuse one schema for request + response.

## File Location

`backend/app/api/schemas/<feature>.py` — one file per feature.

## Forbidden in Response Schemas

- `password`, `password_hash`, `hashed_password`
- `access_token`, `refresh_token`, `session_id`
- internal audit cols if not user-facing (`created_by_internal_id`, raw FKs)
- `is_superuser`, `is_admin` unless caller admin

## Example

```python
# WRONG: one schema for everything → leaks hash on response, allows id on create
from pydantic import BaseModel

class User(BaseModel):
    id: int | None = None
    email: str
    password_hash: str       # leaks on response
    is_superuser: bool       # client can self-promote on create
```

```python
# CORRECT: 3 schemas, validated boundaries
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=200)

class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
```

## Constraints via `Field`

Use Pydantic field constraints, not hand-rolled validation.

```python
# WRONG: imperative validation in handler
if len(payload.name) < 1 or len(payload.name) > 200:
    raise HTTPException(422, "bad name")

# CORRECT: declared in schema, FastAPI returns 422 automatically
class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list, max_length=10)
```

## Related

- DTO rule: [python/patterns.md](../python/patterns.md) — TypedDict (internal) vs Pydantic (boundary)
- Route handler uses these schemas: [routes.md](./routes.md)