"""File processing module — content detection, extraction, and service orchestration."""

from backend.app.file_processing.detect import detect_file_group
from backend.app.file_processing.extract import (
    extract_pdf_text,
    extract_text,
    validate_image,
)
from backend.app.file_processing.service import process_file
from backend.app.file_processing.types import FileGroup, ProcessedInput

__all__ = [
    "FileGroup",
    "ProcessedInput",
    "detect_file_group",
    "extract_pdf_text",
    "extract_text",
    "process_file",
    "validate_image",
]
