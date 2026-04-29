from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import mimetypes
import os

from .config import (
    ARCHIVE_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    PDF_EXTENSIONS,
    TEXT_EXTENSIONS,
)


@dataclass
class ExtractedContent:
    text: str
    mime_type: str
    extractor: str
    error: str = ""


def detect_mime_type(path: Path) -> str:
    try:
        import magic  # type: ignore

        return magic.Magic(mime=True).from_file(str(path)) or "application/octet-stream"
    except Exception:
        guessed, _ = mimetypes.guess_type(str(path))
        if guessed:
            return guessed
        suffix = path.suffix.lower()
        if suffix in PDF_EXTENSIONS:
            return "application/pdf"
        if suffix in IMAGE_EXTENSIONS:
            return "image/unknown"
        if suffix in ARCHIVE_EXTENSIONS:
            return "application/archive"
        if suffix in MEDIA_EXTENSIONS:
            return "media/unknown"
        if suffix in TEXT_EXTENSIONS:
            return "text/plain"
        return "application/octet-stream"


def extract_text(path: Path, max_chars: int = 12000) -> ExtractedContent:
    path = Path(path)
    mime_type = detect_mime_type(path)
    suffix = path.suffix.lower()

    if suffix in PDF_EXTENSIONS or mime_type == "application/pdf":
        return _extract_pdf(path, mime_type, max_chars)

    if suffix in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return _extract_image(path, mime_type, max_chars)

    if suffix in TEXT_EXTENSIONS or mime_type.startswith("text/"):
        return _extract_text_file(path, mime_type, max_chars)

    if suffix in ARCHIVE_EXTENSIONS:
        return ExtractedContent("", mime_type, "metadata", "Archive content extraction is not enabled.")

    if suffix in MEDIA_EXTENSIONS or mime_type.startswith("audio/") or mime_type.startswith("video/"):
        return ExtractedContent("", mime_type, "metadata", "Media transcription is not enabled.")

    return ExtractedContent("", mime_type, "unsupported", f"Unsupported file type: {mime_type}")


def _extract_text_file(path: Path, mime_type: str, max_chars: int) -> ExtractedContent:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, errors="replace") as handle:
                return ExtractedContent(handle.read(max_chars), mime_type, f"text:{encoding}")
        except Exception as exc:
            last_error = exc
    return ExtractedContent("", mime_type, "text", str(last_error or "Could not read text file."))


def _extract_pdf(path: Path, mime_type: str, max_chars: int) -> ExtractedContent:
    errors = []
    try:
        import pdfplumber  # type: ignore

        chunks = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:20]:
                text = page.extract_text() or ""
                chunks.append(text)
                if sum(len(chunk) for chunk in chunks) >= max_chars:
                    break
        text = "\n".join(chunks).strip()[:max_chars]
        if text:
            return ExtractedContent(text, mime_type, "pdfplumber")
    except Exception as exc:
        errors.append(f"pdfplumber: {exc}")

    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages[:20]:
            chunks.append(page.extract_text() or "")
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
        text = "\n".join(chunks).strip()[:max_chars]
        if text:
            return ExtractedContent(text, mime_type, "PyPDF2")
        errors.append("PyPDF2: no extractable text found")
    except Exception as exc:
        errors.append(f"PyPDF2: {exc}")

    return ExtractedContent("", mime_type, "pdf", "; ".join(errors) or "No PDF text extracted.")


def _extract_image(path: Path, mime_type: str, max_chars: int) -> ExtractedContent:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        tesseract_cmd = os.getenv("TESSERACT_CMD")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        with Image.open(path) as image:
            text = pytesseract.image_to_string(image)
        return ExtractedContent(text.strip()[:max_chars], mime_type, "pytesseract")
    except Exception as exc:
        return ExtractedContent("", mime_type, "pytesseract", str(exc))

