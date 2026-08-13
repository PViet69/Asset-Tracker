"""Request authentication and resource controls."""

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

MAX_REQUEST_SIZE = 250 * 1024 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_REQUESTS = 60


@dataclass
class InMemoryRateLimiter:
    """Thread-safe fixed-window request limiter keyed by client address."""

    _requests: dict[str, deque[float]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - RATE_LIMIT_WINDOW_SECONDS
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= RATE_LIMIT_REQUESTS:
                return False
            timestamps.append(current)
            return True


def require_upload_access(request: Request) -> None:
    """Require configured Bearer API key and allow request under rate limit."""
    configured_key = getattr(request.app.state, "upload_api_key", None)
    if configured_key is None:
        return

    authorization = request.headers.get("authorization", "")
    scheme, _, supplied_key = authorization.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        supplied_key, configured_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    limiter = request.app.state.upload_rate_limiter
    client_host = request.client.host if request.client else "unknown"
    if not limiter.allow(client_host):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )


def reject_oversized_request(request: Request) -> None:
    """Reject declared request bodies before multipart parsing and spooling."""
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        size = int(content_length)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Content-Length") from None
    if size > MAX_REQUEST_SIZE:
        raise HTTPException(status_code=413, detail="Request exceeds 250 MB limit")
