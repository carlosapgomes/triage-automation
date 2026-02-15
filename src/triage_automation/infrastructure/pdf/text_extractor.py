"""PDF text extraction using pypdf."""

from __future__ import annotations

import io

from pypdf import PdfReader


class PdfTextExtractionError(RuntimeError):
    """Raised when PDF bytes cannot be parsed or extracted."""


class PdfTextExtractor:
    """Extract textual content from PDF bytes."""

    def extract_text(self, pdf_bytes: bytes) -> str:
        """Return concatenated page text or raise PdfTextExtractionError."""

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            chunks: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    chunks.append(text)

            return "\n".join(chunks).strip()
        except Exception as error:  # noqa: BLE001
            raise PdfTextExtractionError("Failed to extract text from PDF") from error
