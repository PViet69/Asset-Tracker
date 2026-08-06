# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** - Functions, utilities, components
2. **Integration Tests** - API endpoints, DB ops
3. **E2E Tests** - Critical user flows (framework per language)

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED)
2. Run test - FAIL
3. Minimal impl (GREEN)
4. Run test - PASS
5. Refactor (IMPROVE)
6. Verify coverage (80%+)

## Troubleshooting Test Failures

1. Use **tdd-guide** agent
2. Check test isolation
3. Verify mocks correct
4. Fix impl, not tests (unless tests wrong)

## Agent Support

- **tdd-guide** - Use PROACTIVELY for new features, enforces write-tests-first

## Test Structure (AAA Pattern)

Prefer Arrange-Act-Assert:

```typescript
test('calculates similarity correctly', () => {
  // Arrange
  const vector1 = [1, 0, 0]
  const vector2 = [0, 1, 0]

  // Act
  const similarity = calculateCosineSimilarity(vector1, vector2)

  // Assert
  expect(similarity).toBe(0)
})
```

### Test Naming

Descriptive names explain behavior under test:

```typescript
test('returns empty array when no markets match query', () => {})
test('throws error when API key is missing', () => {})
test('falls back to substring search when Redis is unavailable', () => {})
```