"""Inline local assets and pin a strict CSP before capture.

The browser is configured to abort every http(s) request, so an image or font
that is not embedded as a data URI would silently fail. Doing the resolution in
Python keeps the page self-contained, cacheable and byte-stable.
"""

from __future__ import annotations

import base64
import hashlib
import html as html_module
import logging
import mimetypes
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_SRC = re.compile(r"\bsrc\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
_BASE = re.compile(r"<base\b[^>]*>", re.IGNORECASE)

CSP = (
    "default-src 'none'; "
    "img-src data:; "
    "style-src 'unsafe-inline'; "
    "font-src data:; "
    "script-src 'unsafe-inline'; "
    "connect-src 'none'"
)

_MAX_ASSET_BYTES = 8 * 1024 * 1024


def _mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    return "application/octet-stream"


def data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


class AssetStore:
    """Content-addressed cache for images referenced by a layout.

    Remote URLs are fetched once with the configured user agent, then served as
    data URIs forever. A failed fetch is not retried inside the same process so
    a broken CDN cannot make rendering slow or non-deterministic.
    """

    def __init__(self, root: Path | str, *, fetch_remote: bool = True) -> None:
        self.root = Path(root)
        self.fetch_remote = fetch_remote
        self._failed: set[str] = set()
        self._memory: dict[str, str] = {}

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(url.encode()).hexdigest()
        base = self.root / digest[:2]
        return base / f"{digest}.bin", base / f"{digest}.mime"

    def _cache_get(self, url: str) -> str | None:
        binary, mime_file = self._cache_paths(url)
        if not binary.exists() or not mime_file.exists():
            return None
        try:
            return data_uri(binary.read_bytes(), mime_file.read_text().strip())
        except OSError:
            return None

    def _cache_put(self, url: str, data: bytes, mime: str) -> str:
        binary, mime_file = self._cache_paths(url)
        binary.parent.mkdir(parents=True, exist_ok=True)
        temp = binary.with_suffix(".tmp")
        temp.write_bytes(data)
        temp.replace(binary)
        mime_file.write_text(mime, encoding="ascii")
        return data_uri(data, mime)

    def _fetch(self, url: str) -> str | None:
        if url in self._failed:
            return None
        try:
            import httpx

            with httpx.Client(
                follow_redirects=True,
                timeout=10.0,
                headers={"User-Agent": "SnapToSpotRender/0.1"},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.content
                if len(data) > _MAX_ASSET_BYTES:
                    raise ValueError("asset exceeds render budget")
                mime = response.headers.get("content-type", "").split(";")[0].strip()
                if not mime.startswith("image/"):
                    mime = "image/png"
                return self._cache_put(url, data, mime)
        except Exception as exc:  # noqa: BLE001 - omission is the honest fallback
            logger.info("Render asset unavailable, omitting %s: %s", url, exc)
            self._failed.add(url)
            return None

    def resolve(self, url: str, base_dir: Path | None) -> str | None:
        if not url:
            return None
        if url.startswith("data:"):
            return url
        if url in self._memory:
            return self._memory[url]

        parsed = url.lower()
        if parsed.startswith(("http://", "https://", "//")):
            if not self.fetch_remote:
                return None
            cached = self._cache_get(url)
            resolved = cached if cached is not None else self._fetch(url)
        else:
            raw = url[7:] if url.startswith("file://") else url
            candidate = Path(raw)
            if not candidate.is_absolute() and base_dir is not None:
                candidate = base_dir / candidate
            try:
                resolved = data_uri(candidate.read_bytes(), _mime(candidate))
            except OSError:
                resolved = None
        if resolved is not None:
            self._memory[url] = resolved
        return resolved


def inline_images(
    document: str,
    *,
    base_dir: Path | str | None = None,
    store: AssetStore | None = None,
) -> str:
    """Replace every <img> with a data URI, or a neutral empty frame."""
    base = Path(base_dir) if base_dir is not None else None

    def replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        source = _SRC.search(tag)
        if source is None:
            return tag
        url = html_module.unescape(source.group(2))
        resolved = store.resolve(url, base) if store is not None else None
        if resolved is None and url.startswith("data:"):
            resolved = url
        if resolved is None:
            return '<div class="sts-shot-empty"></div>'
        return _SRC.sub(
            lambda found: f'src="{resolved}"',
            tag,
            count=1,
        )

    return _IMAGE_TAG.sub(replace, document)


def inject_csp(document: str) -> str:
    """Add the capture CSP without disturbing the document's layout."""
    if "Content-Security-Policy" in document:
        return document
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    if "<head" in document.lower():
        return re.sub(r"(<head\b[^>]*>)", r"\1" + meta, document, count=1, flags=re.IGNORECASE)
    return meta + document


def prepare_document(document: str, *, base_dir: Path | str | None = None,
                     store: AssetStore | None = None) -> str:
    return inject_csp(inline_images(document, base_dir=base_dir, store=store))
