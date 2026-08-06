---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

> Extends [common/testing.md](../common/testing.md) with Python content.

## Framework

Use **pytest**.

## Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

## Test Organization

Use `pytest.mark` for categorization:

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...

@pytest.mark.integration
def test_database_connection():
    ...
```

## Reference

See skill: `python-testing` for pytest patterns + fixtures.