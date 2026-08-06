# Common Patterns

## Skeleton Projects

New functionality:
1. Search battle-tested skeleton projects
2. Parallel agents evaluate:
   - Security assessment
   - Extensibility analysis
   - Relevance scoring
   - Implementation planning
3. Clone best match as foundation
4. Iterate within proven structure

## Design Patterns

### Repository Pattern

Encapsulate data access behind consistent interface:
- Standard ops: findAll, findById, create, update, delete
- Concrete impls handle storage (database, API, file, etc.)
- Business logic depends on abstract interface, not storage
- Enables swapping data sources, simplifies mock testing

### API Response Format

Consistent envelope for all API responses:
- Success/status indicator
- Data payload (nullable on error)
- Error message field (nullable on success)
- Metadata for paginated responses (total, page, limit)