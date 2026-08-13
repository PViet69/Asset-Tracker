"""Unit tests for request authentication and body size security controls."""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend.app.security import (
    MAX_REQUEST_SIZE,
    InMemoryRateLimiter,
    reject_oversized_request,
    require_upload_access,
)


def test_reject_oversized_request_allows_valid_content_length() -> None:
    request = Mock()
    request.headers = {"content-length": "1024"}

    # Should not raise
    reject_oversized_request(request)


def test_reject_oversized_request_allows_missing_content_length() -> None:
    request = Mock()
    request.headers = {}

    # Chunked uploads may omit content-length
    reject_oversized_request(request)


def test_reject_oversized_request_raises_413_when_exceeding_max() -> None:
    request = Mock()
    request.headers = {"content-length": str(MAX_REQUEST_SIZE + 1)}

    with pytest.raises(HTTPException) as exc_info:
        reject_oversized_request(request)

    assert exc_info.value.status_code == 413
    assert "250 MB" in exc_info.value.detail


def test_reject_oversized_request_raises_400_for_invalid_content_length() -> None:
    request = Mock()
    request.headers = {"content-length": "not-a-number"}

    with pytest.raises(HTTPException) as exc_info:
        reject_oversized_request(request)

    assert exc_info.value.status_code == 400
    assert "Invalid Content-Length" in exc_info.value.detail


def test_rate_limiter_allows_and_blocks_requests() -> None:
    limiter = InMemoryRateLimiter()

    for _ in range(60):
        assert limiter.allow("client-ip-1") is True

    # 61st request should be blocked
    assert limiter.allow("client-ip-1") is False
    # Different client IP should still be allowed
    assert limiter.allow("client-ip-2") is True


def test_require_upload_access_passes_when_no_api_key_configured() -> None:
    request = Mock()
    request.app.state.upload_api_key = None

    # Should not raise
    require_upload_access(request)


def test_require_upload_access_raises_401_on_missing_or_invalid_bearer() -> None:
    request = Mock()
    request.app.state.upload_api_key = "secret-key"
    request.headers = {"authorization": "Bearer wrong-key"}

    with pytest.raises(HTTPException) as exc_info:
        require_upload_access(request)

    assert exc_info.value.status_code == 401
