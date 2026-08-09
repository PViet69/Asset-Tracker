"""Service-level file processing orchestration."""

from backend.app.exceptions import FileProcessingError
from backend.app.file_processing.detect import detect_file_group
from backend.app.file_processing.extract import (
    extract_pdf_text,
    extract_text,
    validate_image,
)
from backend.app.file_processing.types import FileGroup, ProcessedInput

# 25 MB limit
MAX_FILE_SIZE = 25 * 1024 * 1024


def process_file(content: bytes, filename: str, content_type: str) -> ProcessedInput:
    """Process uploaded file bytes into a typed input.

    Validates size, detects file group, extracts content, returns ProcessedInput.

    Args:
        content: Raw file bytes.
        filename: Original filename (for context, not used as path).
        content_type: MIME content-type from upload (ignored for detection).

    Returns:
        ProcessedInput with kind and value.

    Raises:
        FileProcessingError: if empty, too large, or unsupported type.
    """
    if not content:
        raise FileProcessingError("Empty file")

    if len(content) > MAX_FILE_SIZE:
        raise FileProcessingError("File exceeds 25 MB limit")

    group: FileGroup = detect_file_group(content)

    if group == "text":
        return ProcessedInput(kind="text", value=extract_text(content))

    if group == "image":
        validate_image(content)
        return ProcessedInput(kind="image", value=content)

    # PDF: extract text
    text = extract_pdf_text(content)
    return ProcessedInput(kind="text", value=text)
