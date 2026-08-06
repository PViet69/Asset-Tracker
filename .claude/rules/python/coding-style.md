---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> Extends [common/coding-style.md](../common/coding-style.md) with Python content.

## Standards

- Follow **PEP 8**
- **Type annotations** on all function signatures

## Immutability

Prefer immutable structures:

```python
# WRONG: mutable dataclass — silent shared-state bugs
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str

u = User("a", "a@x.com")
u.name = "b"  # mutation in-place

# CORRECT: frozen dataclass
@dataclass(frozen=True)
class User:
    name: str
    email: str

u = User("a", "a@x.com")
u2 = replace(u, name="b")  # new instance

# CORRECT: NamedTuple for lightweight value
from typing import NamedTuple

class Point(NamedTuple):
    x: float
    y: float

# CORRECT: Pydantic with frozen for validated DTOs
from pydantic import BaseModel, ConfigDict

class Account(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    email: str
```

## Formatting

- **uv run ruff format** — format code
- **uv run ruff check --select I --fix** — sort imports
- **uv run ruff check** — lint

## Reference

Skill `python-patterns` for full Python idioms + patterns.