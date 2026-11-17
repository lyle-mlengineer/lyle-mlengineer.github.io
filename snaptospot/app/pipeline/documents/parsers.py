"""Structure-aware parsers for every supported upload type.

Each parser returns pages (slides, sections, CSV blocks or images) so a fact can
cite the page it came from. Parsing failures are converted into
:class:`DocumentError` with a page number where possible; the caller records the
failure and lets the gap move on.
"""

import csv
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import PurePath

from app.config import get_settings
from app.pipeline.documents import security
from app.pipeline.documents.errors import (
    DocumentError,
    MalformedDocument,
    PageLimitExceeded,
    UnsupportedDocument,
)


@dataclass
class ParsedPage:
    number: int
    kind: str
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage] = field(default_factory=list)
    mime: str = ""
    notes: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _pages_from_sections(
    filename: str,
    sections: list[tuple[str, str]],
    *,
    kind: str,
    unit: str,
) -> ParsedDocument:
    limit = get_settings().max_document_pages
    nonempty = [(title, text) for title, text in sections if (title + text).strip()]
    if len(nonempty) > limit:
        raise PageLimitExceeded(len(nonempty), limit, unit=unit)
    pages = []
    for index, (title, text) in enumerate(nonempty, start=1):
        body = _clean(f"{title}\n{text}" if title else text)
        if body:
            pages.append(ParsedPage(number=index, kind=kind, text=body))
    if not pages:
        raise DocumentError(f"{filename}: the document contains no extractable text")
    return ParsedDocument(pages=pages, mime="")


def parse_pdf(data: bytes, filename: str) -> ParsedDocument:
    from pypdf import PdfReader

    limit = get_settings().max_document_pages
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # pragma: no cover - provider specific
                raise DocumentError(f"{filename}: password-protected PDF") from exc
        count = len(reader.pages)
    except DocumentError:
        raise
    except Exception as exc:
        raise MalformedDocument(filename, str(exc) or "could not read PDF pages") from exc

    if count > limit:
        raise PageLimitExceeded(count, limit, unit="pages")

    pages: list[ParsedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise MalformedDocument(
                filename, f"page {number} could not be read: {exc}"
            ) from exc
        cleaned = _clean(text)
        if cleaned:
            pages.append(ParsedPage(number=number, kind="page", text=cleaned))

    if not pages:
        suffix = "enable OCR for scanned PDFs" if not get_settings().ocr_enabled else (
            "OCR found no text"
        )
        raise DocumentError(f"{filename}: no extractable text ({suffix})")
    return ParsedDocument(pages=pages, mime=security.PDF)


def parse_docx(data: bytes, filename: str) -> ParsedDocument:
    from docx import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = DocxDocument(BytesIO(data))
    except Exception as exc:
        raise MalformedDocument(filename, str(exc) or "could not open DOCX") from exc

    sections: list[tuple[str, str]] = []
    title = ""
    body: list[str] = []

    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name or "").lower() if paragraph.style else ""
            if style.startswith("heading") and (title or body):
                sections.append((title, "\n".join(body)))
                title, body = text, []
            elif style.startswith("heading"):
                title = text
            else:
                body.append(text)
        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    body.append(" | ".join(cells))

    if title or body:
        sections.append((title, "\n".join(body)))
    return _pages_from_sections(filename, sections, kind="section", unit="sections")


def _shape_text(shape: object) -> list[str]:
    texts: list[str] = []
    has_text = getattr(shape, "has_text_frame", False)
    if has_text:
        for paragraph in shape.text_frame.paragraphs:
            text = "".join(run.text for run in paragraph.runs).strip()
            if text:
                texts.append(text)
    has_table = getattr(shape, "has_table", False)
    if has_table:
        for row in shape.table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                texts.append(" | ".join(cells))
    child_shapes = getattr(shape, "shapes", None)
    if child_shapes is not None:
        for child in child_shapes:
            texts.extend(_shape_text(child))
    return texts


def parse_pptx(data: bytes, filename: str) -> ParsedDocument:
    from pptx import Presentation

    limit = get_settings().max_document_pages
    try:
        presentation = Presentation(BytesIO(data))
        slides = list(presentation.slides)
    except Exception as exc:
        raise MalformedDocument(filename, str(exc) or "could not open PPTX") from exc

    if len(slides) > limit:
        raise PageLimitExceeded(len(slides), limit, unit="slides")

    pages: list[ParsedPage] = []
    for number, slide in enumerate(slides, start=1):
        texts: list[str] = []
        for shape in slide.shapes:
            texts.extend(_shape_text(shape))
        try:
            notes = slide.notes_slide.notes_text_frame.text
        except Exception:  # pragma: no cover - notes are optional
            notes = ""
        if notes and notes.strip():
            texts.append(notes.strip())
        cleaned = _clean("\n".join(dict.fromkeys(texts)))
        if cleaned:
            pages.append(ParsedPage(number=number, kind="slide", text=cleaned))

    if not pages:
        raise DocumentError(f"{filename}: slides contain no extractable text")
    return ParsedDocument(pages=pages, mime=security.PPTX)


def _text_body(data: bytes, filename: str) -> str:
    try:
        return security.decode_text(data) or ""
    except Exception as exc:  # pragma: no cover - defensive
        raise UnsupportedDocument(f"{filename}: could not decode text") from exc


def parse_markdown(data: bytes, filename: str) -> ParsedDocument:
    text = _text_body(data, filename)
    sections: list[tuple[str, str]] = []
    title = ""
    body: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if title or body:
                sections.append((title, "\n".join(body)))
            title, body = heading, []
        elif stripped:
            body.append(stripped)
    if title or body:
        sections.append((title, "\n".join(body)))
    return _pages_from_sections(filename, sections, kind="section", unit="sections")


def parse_text(data: bytes, filename: str) -> ParsedDocument:
    text = _text_body(data, filename)
    chunks = [part for part in text.split("\f") if part.strip()]
    if not chunks:
        raise DocumentError(f"{filename}: the file is empty")
    sections = [("", part) for part in chunks]
    return _pages_from_sections(filename, sections, kind="page", unit="pages")


def parse_csv(data: bytes, filename: str) -> ParsedDocument:
    text = _text_body(data, filename)
    try:
        rows = list(csv.reader(StringIO(text)))
    except csv.Error as exc:
        raise MalformedDocument(filename, str(exc)) from exc
    if not rows:
        raise DocumentError(f"{filename}: the CSV is empty")

    limit = get_settings().max_document_pages
    page_size = 50
    header = [cell.strip() for cell in rows[0]]
    pages: list[ParsedPage] = []
    for start in range(1, len(rows), page_size):
        block = rows[start : start + page_size]
        lines = []
        for row in block:
            cells = []
            for index, value in enumerate(row):
                value = value.strip()
                if not value:
                    continue
                key = header[index] if index < len(header) and header[index] else f"col{index + 1}"
                cells.append(f"{key}: {value}")
            if cells:
                lines.append("; ".join(cells))
        if lines:
            pages.append(
                ParsedPage(
                    number=len(pages) + 1,
                    kind="rows",
                    text=_clean("\n".join(lines)),
                )
            )
        if len(pages) > limit:
            raise PageLimitExceeded(len(pages), limit, unit="pages")
    if not pages:
        raise DocumentError(f"{filename}: the CSV has no data rows")
    return ParsedDocument(pages=pages, mime=security.CSV)


def parse_image(data: bytes, filename: str) -> ParsedDocument:
    settings = get_settings()
    if not settings.ocr_enabled:
        raise DocumentError(
            f"{filename}: OCR is disabled; set SNAP_OCR_ENABLED=true to read images"
        )
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise DocumentError(
            f"{filename}: OCR needs pytesseract and Pillow installed"
        ) from exc

    try:
        with Image.open(BytesIO(data)) as image:
            text = pytesseract.image_to_string(image)
    except Exception as exc:
        raise DocumentError(f"{filename}: OCR failed ({exc})") from exc
    cleaned = _clean(text)
    if not cleaned:
        raise DocumentError(f"{filename}: OCR found no text")
    return ParsedDocument(
        pages=[ParsedPage(number=1, kind="image", text=cleaned)], mime=""
    )


def parse_document(data: bytes, mime: str, filename: str) -> ParsedDocument:
    if mime == security.PDF:
        parsed = parse_pdf(data, filename)
    elif mime == security.DOCX:
        parsed = parse_docx(data, filename)
    elif mime == security.PPTX:
        parsed = parse_pptx(data, filename)
    elif mime == security.MARKDOWN:
        parsed = parse_markdown(data, filename)
    elif mime == security.CSV:
        parsed = parse_csv(data, filename)
    elif mime in security.IMAGE_MIMES:
        parsed = parse_image(data, filename)
    elif mime == security.PLAIN:
        parsed = parse_text(data, filename)
    else:
        raise UnsupportedDocument(f"{filename}: unsupported MIME type {mime}")
    parsed.mime = mime
    return parsed


def source_label(filename: str, page: int, kind: str) -> str:
    """Human-readable citation suffix, e.g. ``deck.pptx, slide 7``."""
    noun = {
        "slide": "slide",
        "section": "section",
        "rows": "rows page",
        "image": "image",
    }.get(kind, "page")
    return f"{PurePath(filename).name}, {noun} {page}"
