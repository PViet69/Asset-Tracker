"""Boundary-level file processing service tests."""

import pytest

from backend.app.exceptions import FileProcessingError
from backend.app.file_processing.service import process_file


@pytest.mark.unit
def test_rejects_empty_file():
    with pytest.raises(FileProcessingError, match="Empty file"):
        process_file(b"", "empty.txt", "text/plain")


@pytest.mark.unit
def test_rejects_file_over_25_mb():
    content = b"x" * (25 * 1024 * 1024 + 1)
    with pytest.raises(FileProcessingError, match="25 MB"):
        process_file(content, "large.txt", "text/plain")
