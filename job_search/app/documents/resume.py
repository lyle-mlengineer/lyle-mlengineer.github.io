"""Canonical resume identity and artifact names."""

from __future__ import annotations

import re

from ..utils import slugify

NAME = "LYLE OKOTH"
PHONE = "+254 797 668 066"
EMAIL = "lyleokoth.mlengineer@gmail.com"
LOCATION = "Nairobi, Kenya"
LINKS: tuple[tuple[str, str], ...] = (
    ("linkedin.com/in/lyle-okoth", "https://www.linkedin.com/in/lyle-okoth/"),
    ("github.com/lyle-mlengineer", "https://github.com/lyle-mlengineer"),
    ("lyle-mlengineer.github.io", "https://lyle-mlengineer.github.io"),
    ("medium.com/@lyle-okoth", "https://medium.com/@lyle-okoth"),
)
CONTACT_LINE = f"{LOCATION}  |  {PHONE}  |  {EMAIL}"


def artifact_filename(company: str | None, role: str | None, version: int, extension: str) -> str:
    """LYLE-OKOTH-<COMPANY>-<ROLE>-CV-v<n>.<ext>, ATS-safe and bounded."""
    parts = [part for part in (company or "", role or "") if part.strip()]
    middle = "-".join(parts) or "TAILORED"
    slug = slugify(middle, fallback="TAILORED").upper()
    slug = re.sub(r"[^A-Z0-9]+", "-", slug).strip("-")[:90].strip("-")
    extension = extension.lstrip(".").lower()
    return f"LYLE-OKOTH-{slug}-CV-v{version}.{extension}"
