"""Text and PDF extraction tests."""

from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfWriter

from backend.app.exceptions import FileProcessingError
from backend.app.file_processing.extract import (
    extract_pdf_text,
    extract_text,
    validate_image,
)


@pytest.mark.unit
def test_decodes_utf8_text():
    assert extract_text("café".encode()) == "café"


@pytest.mark.unit
def test_rejects_invalid_utf8():
    with pytest.raises(FileProcessingError, match="decode"):
        extract_text(b"\xff\xfe")


@pytest.mark.unit
def test_validates_image_bytes():
    output = BytesIO()
    Image.new("RGB", (1, 1), "blue").save(output, format="PNG")
    validate_image(output.getvalue())


@pytest.mark.unit
def test_rejects_invalid_image_bytes():
    with pytest.raises(FileProcessingError, match="image"):
        validate_image(b"not image bytes")


# Minimal PDF with extractable text content
_MINIMAL_TEXT_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
    b"  /Resources << /Font << /F1 4 0 R >> >>\n"
    b"  /Contents 5 0 R >> endobj\n"
    b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
    b"5 0 obj << /Length 44 >> stream\n"
    b"BT /F1 12 Tf 100 700 Td (Hello World) Tj ET\n"
    b"endstream endobj\n"
    b"xref\n0 6\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000266 00000 n \n"
    b"0000000346 00000 n \n"
    b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n432\n%%EOF\n"
)


@pytest.mark.unit
def test_extract_text_from_pdf_with_content():
    text = extract_pdf_text(_MINIMAL_TEXT_PDF)
    assert "Hello World" in text


@pytest.mark.unit
def test_blank_pdf_raises():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)

    with pytest.raises(FileProcessingError, match="PDF has no extractable text"):
        extract_pdf_text(stream.getvalue())


@pytest.mark.unit
def test_malformed_pdf_raises_file_processing_error():
    with pytest.raises(FileProcessingError, match="Invalid PDF"):
        extract_pdf_text(b"%PDF-1.4 malformed data stream header")


@pytest.mark.unit
def test_extract_pdf_text_preserves_page_boundaries(monkeypatch: pytest.MonkeyPatch):
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _stream: object) -> None:
            self.pages = [FakePage("Page 1 content"), FakePage("Page 2 content")]

    monkeypatch.setattr("backend.app.file_processing.extract.PdfReader", FakeReader)

    result = extract_pdf_text(_MINIMAL_TEXT_PDF)
    assert result == "Page 1 content\n\nPage 2 content"
