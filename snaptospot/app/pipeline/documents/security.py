"""MIME sniffing, decompression guards and the malware hook.

The browser's ``Content-Type`` is never trusted. A file is classified from its
bytes, checked for archive bombs and active content, then handed to a parser.
ClamAV or an equivalent scanner can replace :func:`scan_bytes` behind the same
contract: raise :class:`MalwareDetected` to reject the upload.
"""

import re
import zipfile
from io import BytesIO
from pathlib import PurePath

from app.config import get_settings
from app.pipeline.documents.errors import (
    DocumentError,
    MalformedDocument,
    MalwareDetected,
    UnsupportedDocument,
)

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MARKDOWN = "text/markdown"
PLAIN = "text/plain"
CSV = "text/csv"
PNG = "image/png"
JPEG = "image/jpeg"
GIF = "image/gif"
WEBP = "image/webp"

TEXT_MIMES = {MARKDOWN, PLAIN, CSV}
IMAGE_MIMES = {PNG, JPEG, GIF, WEBP}
SUPPORTED_MIMES = TEXT_MIMES | IMAGE_MIMES | {PDF, DOCX, PPTX}

_EXTENSION_MIME = {
    ".pdf": PDF,
    ".docx": DOCX,
    ".pptx": PPTX,
    ".md": MARKDOWN,
    ".markdown": MARKDOWN,
    ".txt": PLAIN,
    ".text": PLAIN,
    ".csv": CSV,
    ".png": PNG,
    ".jpg": JPEG,
    ".jpeg": JPEG,
    ".gif": GIF,
    ".webp": WEBP,
}
MIME_EXTENSION = {
    PDF: ".pdf",
    DOCX: ".docx",
    PPTX: ".pptx",
    MARKDOWN: ".md",
    PLAIN: ".txt",
    CSV: ".csv",
    PNG: ".png",
    JPEG: ".jpg",
    GIF: ".gif",
    WEBP: ".webp",
}

_EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe")
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ACTIVE_EXTENSIONS = (
    ".exe",
    ".dll",
    ".scr",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
    ".msi",
)
_EICAR = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._ ()\[\]-]+")


def safe_filename(name: str) -> str:
    """Keep the display name, never the uploader's path."""
    base = PurePath((name or "").replace("\\", "/")).name
    base = _UNSAFE_NAME.sub("_", base).strip(" ._")
    return (base or "upload")[:120]


def decode_text(data: bytes) -> str | None:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" in text:
            return None
        controls = sum(
            1 for char in text if ord(char) < 32 and char not in "\t\n\r\f"
        )
        if controls and controls / max(len(text), 1) > 0.01:
            return None
        return text
    return None


def _sniff_zip(data: bytes, filename: str) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        raise UnsupportedDocument(f"{filename}: corrupt ZIP container") from exc
    if "[Content_Types].xml" not in names:
        raise UnsupportedDocument(f"{filename}: not a DOCX or PPTX package")
    if any(name.startswith("word/") for name in names):
        return DOCX
    if any(name.startswith("ppt/") for name in names):
        return PPTX
    raise UnsupportedDocument(f"{filename}: unsupported Office package")


def sniff_mime(data: bytes, filename: str) -> str:
    """Classify by signature first and extension second."""
    name = safe_filename(filename)
    ext = PurePath(name).suffix.lower()

    if data.startswith(b"%PDF-"):
        mime = PDF
    elif data.startswith(b"PK\x03\x04"):
        mime = _sniff_zip(data, name)
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = PNG
    elif data.startswith(b"\xff\xd8\xff"):
        mime = JPEG
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mime = GIF
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = WEBP
    elif data.startswith(_EXECUTABLE_MAGIC) or data.startswith(_OLE_MAGIC):
        raise UnsupportedDocument(f"{name}: executable or legacy Office file rejected")
    else:
        text = decode_text(data)
        if text is None:
            raise UnsupportedDocument(f"{name}: unrecognised binary content")
        if ext == ".csv":
            mime = CSV
        elif ext in {".md", ".markdown"}:
            mime = MARKDOWN
        elif ext in {".txt", ".text"} or not ext:
            mime = PLAIN
        elif _EXTENSION_MIME.get(ext) is not None:
            # Let the extension check below report the mismatch clearly.
            mime = PLAIN
        else:
            raise UnsupportedDocument(f"{name}: {ext or 'unknown'} is not supported")

    expected = _EXTENSION_MIME.get(ext)
    if expected is not None and expected != mime:
        if not (expected in TEXT_MIMES and mime in TEXT_MIMES):
            raise UnsupportedDocument(
                f"{name}: content does not match the .{ext.lstrip('.')} extension"
            )
    if mime not in SUPPORTED_MIMES:
        raise UnsupportedDocument(f"{name}: {mime} is not supported")
    return mime


def zip_guard(
    data: bytes,
    *,
    max_uncompressed: int | None = None,
    max_entries: int = 5000,
    max_ratio: int = 200,
) -> None:
    """Reject archives that would expand into a memory or disk bomb."""
    limit = max_uncompressed or get_settings().max_document_uncompressed_bytes
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise DocumentError("corrupt archive") from exc

    if len(infos) > max_entries:
        raise DocumentError(f"archive contains more than {max_entries} entries")

    total = 0
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in PurePath(name).parts:
            raise DocumentError("archive contains an unsafe path")
        if info.flag_bits & 0x1:
            raise DocumentError("archive is encrypted")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise DocumentError("archive contains a symbolic link")
        if name.lower().endswith(".zip"):
            raise DocumentError("nested archives are not allowed")
        if info.file_size > limit:
            raise DocumentError("archive entry expands beyond the size limit")
        total += info.file_size

    if total > limit:
        raise DocumentError(
            f"document expands to {total // (1024 * 1024)} MB, above the "
            f"{limit // (1024 * 1024)} MB limit"
        )
    if total > 5 * 1024 * 1024 and total / max(len(data), 1) > max_ratio:
        raise DocumentError("document has a suspicious compression ratio")


def scan_bytes(data: bytes, mime: str, filename: str) -> None:
    """Malware hook. Raises when the payload must not be stored."""
    if _EICAR in data:
        raise MalwareDetected(f"{filename}: malware signature detected")
    if data.startswith(_EXECUTABLE_MAGIC):
        raise MalwareDetected(f"{filename}: executable payload detected")

    if mime in {DOCX, PPTX}:
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                names = [name.lower() for name in archive.namelist()]
        except zipfile.BadZipFile as exc:
            raise MalformedDocument(filename, "corrupt ZIP package") from exc
        if any(name.endswith("/vbaproject.bin") for name in names):
            raise MalwareDetected(f"{filename}: macro-enabled documents are rejected")
        if any(name.endswith(_ACTIVE_EXTENSIONS) for name in names):
            raise MalwareDetected(f"{filename}: active content inside the package")

    if mime == PDF:
        if b"/JavaScript" in data or b"/Launch" in data:
            raise MalwareDetected(f"{filename}: PDF contains active JavaScript")
