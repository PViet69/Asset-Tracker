"""Content extraction utilities for text, image, and PDF file groups."""

from io import BytesIO

from PIL import Image
from pypdf import PdfReader

from backend.app.exceptions import FileProcessingError


def extract_text(content: bytes) -> str:
    """Decode raw bytes as UTF-8 text.

    Raises:
        FileProcessingError: if bytes are not valid UTF-8.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileProcessingError("Failed to decode text as UTF-8") from exc


def validate_image(content: bytes) -> None:
    """Validate that bytes represent a parseable image.

    Raises:
        FileProcessingError: if image bytes are corrupt.
    """
    try:
        with Image.open(BytesIO(content)) as img:
            img.verify()
    except Exception as exc:
        raise FileProcessingError("Invalid image") from exc


def extract_pdf_text(content: bytes) -> str:
    """Extract all text content from PDF bytes.

    Raises:
        FileProcessingError: if PDF has no extractable text.
    """
    reader = PdfReader(BytesIO(content))
    text_parts: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    full_text = "".join(text_parts).strip()

    if not full_text:
        raise FileProcessingError("PDF has no extractable text")

    return full_text
