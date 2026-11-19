"""Small deterministic helpers shared by ingestion, skills and the API."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"gclid", "fbclid", "ref", "source", "mc_cid", "mc_eid"}
_LEGAL_SUFFIXES = re.compile(
    r"\b(?:ltd|limited|inc|incorporated|llc|plc|gmbh|ag|sa|sas|bv|oy|pty|corp|corporation|co)\b\.?",
    re.IGNORECASE,
)
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def slugify(value: str, *, fallback: str = "item", max_len: int = 60) -> str:
    slug = _NON_SLUG.sub("-", value.lower()).strip("-")
    return (slug[:max_len].strip("-") or fallback)


def clean_text(value: str) -> str:
    return _WS.sub(" ", value or "").strip()


def normalize_company(name: str) -> str:
    cleaned = clean_text(name)
    cleaned = _LEGAL_SUFFIXES.sub("", cleaned)
    cleaned = clean_text(cleaned).strip(" ,.-")
    return cleaned[:200] or "Unknown company"


def fingerprint(company: str, title: str, location: str | None) -> str:
    return sha1(
        "|".join(
            (
                normalize_company(company).lower(),
                clean_text(title).lower(),
                clean_text(location or "").lower(),
            )
        )
    )


def canonicalize_url(url: str) -> str:
    """Lowercase the scheme/host, drop fragments and tracking parameters."""
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only http and https links are supported.")
    if not parsed.hostname:
        raise ValueError("That link has no hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Links with embedded credentials are not allowed.")

    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((scheme, host, parsed.path or "/", urlencode(query), ""))


def provisional_title(text: str) -> str:
    for line in (text or "").splitlines():
        line = clean_text(line)
        if len(line) >= 4:
            return line[:200]
    return "Untitled role"
