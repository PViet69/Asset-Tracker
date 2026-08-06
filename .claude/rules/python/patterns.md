---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Patterns

> Extends [common/patterns.md](../common/patterns.md) with Python content.

## Protocol (Duck Typing)

```python
from typing import Protocol

class Repository(Protocol):
    def find_by_id(self, id: str) -> dict | None: ...
    def save(self, entity: dict) -> dict: ...
```

## DTO Rule

Structured data crossing function/module boundaries = `TypedDict` (internal) or Pydantic `BaseModel` (validated boundary). Never plain `dict[str, X]` as DTO type.

- `TypedDict` — internal, typed, zero-runtime-cost
- Pydantic `BaseModel` — API boundary, config, external data; validates + serializes

```python
# WRONG: plain dict — keys untyped, drift-prone
def save(user: dict) -> dict: ...

# CORRECT: TypedDict for internal pass-through
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    email: str

def save(user: UserDict) -> UserDict: ...

# CORRECT: Pydantic at boundaries
from pydantic import BaseModel

class User(BaseModel):
    id: int
    email: str

def save(user: User) -> User: ...
```

## Pydantic as DTOs

```python
# WRONG: hand-written validation, drift-prone
def create_user(payload: dict) -> dict:
    if not payload.get("name"):
        raise ValueError("name required")
    if "@" not in payload.get("email", ""):
        raise ValueError("invalid email")
    return payload

# CORRECT: Pydantic validates + types in one place
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    age: int | None = Field(default=None, ge=0)
```

- Validate at system boundaries (API, config, external data)
- `model_config = ConfigDict(frozen=True)` for immutable DTOs
- Prefer `BaseModel` over `dataclass` when validation/serialization needed

## Context Managers & Generators

- Context managers (`with`) for resource management
- Generators for lazy evaluation, memory-efficient iteration

## Reference

See skill: `python-patterns` for full patterns — decorators, concurrency, package organization.