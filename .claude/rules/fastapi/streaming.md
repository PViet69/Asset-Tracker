---
paths:
  - "backend/app/api/routes/**/*.py"
---
# Streaming Responses (SSE)

Extends [index.md](./index.md).

## Opt out of compression middleware

```
RULE:
  if response is StreamingResponse and media_type == "text/event-stream":
    headers["Content-Encoding"] = "identity"

WHY GZipMiddleware breaks SSE:
  buffer until len(bytes) >= minimum_size (default=1000) -> emit
  effects on SSE (events typically <200 bytes):
    - first_event delayed until buffer_fills
    - bursty delivery, not real-time
    - browser_sse_parser confused (gzip_frames vs sse_frames)
    - short_turn under threshold -> single burst at close -> looks unstreamed
```

### Required pattern

```python
return StreamingResponse(
    generator(),
    media_type="text/event-stream",
    headers={"Content-Encoding": "identity"},
)
```

```
INVARIANT:
  Starlette.GZipMiddleware: if "Content-Encoding" in headers -> skip compress
  gzip remains active for: HTML, JSON, static bundles
```

### Optional: reverse-proxy buffering

```
IF proxy in {nginx, cloudflare, traefik, ingress} in front of app:
  add header "X-Accel-Buffering: no"   # nginx-family disables buffering
  cost: 0, downside: none
```

```python
headers={
    "Content-Encoding": "identity",
    "X-Accel-Buffering": "no",
}
```

### Don't try "streaming gzip"

```
ANTI-PATTERN: gzip.GzipFile + Z_SYNC_FLUSH per chunk
  cost  = CPU per chunk
  gain  = negligible (sub-KB events)
  verdict = SSE chunks != bandwidth bottleneck

IF compress_streaming_data is real_need:
  prefer protocol_level: HTTP/2 | WebSocket permessage-deflate
  reject middleware_hacks
```

## Yield discipline

```
FOR each yield in generator:
  produce one complete SSE frame, terminator = "\n\n"

HELPER:
  create_data_stream_chunk(data) -> f"data: {json.dumps(data)}\n\n"
  use_helper instead of hand_format per call_site

FORBID:
  await blocking_work on event_loop_thread
USE:
  await asyncio.to_thread(blocking_work)
  -> client disconnect (GeneratorExit) lands at await boundary

WRAP loop_body:
  try: ... finally: cancel(server_resources)
  # BQ jobs, DB cursors, subprocess handles
```

## Testing

```
test_sse_route:
  client = httpx.AsyncClient(stream=True)
  assert per_chunk_emission
  assert response.headers["content-encoding"] == "identity"  # regression guard
  if short_stream:
    assert events_arrive_incrementally
    reject all_at_once_after_close
```
