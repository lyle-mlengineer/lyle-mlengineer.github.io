"""Turn the stored email artifact into the parts a mail client shows.

The model writes one plain-text body: sometimes with blank lines and a
signature, often as one run-on paragraph. Nothing here rewrites the words; it
only separates the greeting, the body paragraphs, the sign-off and the
attachments so the job page can render a real email instead of a text blob.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..jobs.render import split_paragraphs

_GREETING = re.compile(
    r"^(?P<greeting>(?:Dear|Hi|Hello|Good (?:morning|afternoon))\b[^,.:\n]{0,80}[,:.])[ \t]*",
    re.IGNORECASE,
)
_SIGN_OFF = re.compile(
    r"(?is)^(?P<phrase>best regards|kind regards|warm regards|regards|sincerely|"
    r"many thanks|thanks|best|cheers)\s*,?\s*(?P<name>[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){0,3})?\.?$"
)
_SIGN_OFF_LINE = re.compile(
    r"(?im)^\s*(?P<phrase>best regards|kind regards|warm regards|regards|sincerely|"
    r"many thanks|thanks|best|cheers)\s*,?\s*(?P<name>[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){0,3})?\.?\s*$"
)
_ATTACHMENTS_LINE = re.compile(r"(?im)^\s*attachments?\s*:.*$")
_ATTACHMENTS_TAIL = re.compile(r"(?is)\s+attachments?\s*:\s*[^\n]+$")
_NAME = re.compile(r"^[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,3}$")


@dataclass(frozen=True)
class EmailView:
    greeting: str
    paragraphs: list[str] = field(default_factory=list)
    sign_off: str = "Best regards,"
    signature: str = "Lyle Okoth"
    attachments: list[str] = field(default_factory=list)
    to_label: str = "Hiring team"


def format_email(
    body: str,
    *,
    subject: str = "",
    attachments: list[str] | None = None,
    company: str = "",
    sender: str = "Lyle Okoth",
) -> EmailView:
    """Split a stored body into greeting, paragraphs, sign-off and signature."""
    text = _clean(body)
    text = _remove_attachments(text)

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]

    sign_off = ""
    signature = ""
    if blocks:
        match = _SIGN_OFF.match(blocks[-1])
        if match:
            sign_off = _phrase(match.group("phrase"))
            signature = (match.group("name") or "").strip()
            blocks.pop()
        elif len(blocks) > 1 and _NAME.match(blocks[-1]) and len(blocks[-1].split()) <= 4:
            signature = blocks.pop().strip().rstrip(".")
    if not sign_off:
        match = _SIGN_OFF_LINE.search(text)
        if match and match.end() > len(text) - 80:
            sign_off = _phrase(match.group("phrase"))
            signature = (match.group("name") or signature).strip()
            text = text[: match.start()].strip()

    if not blocks:
        blocks = [text]

    greeting = "Dear Hiring Team,"
    first = blocks[0]
    match = _GREETING.match(first)
    if match:
        greeting = match.group("greeting").strip()
        remainder = first[match.end() :].strip()
        blocks = ([remainder] if remainder else []) + blocks[1:]

    body_text = "\n\n".join(blocks).strip()
    # Aim for roughly three paragraphs, but never make tiny 40-character lines.
    limit = max(160, min(420, len(body_text) // 3))
    paragraphs = [
        paragraph.strip()
        for paragraph in (
            blocks if len(blocks) > 1 else split_paragraphs(body_text, limit)
        )
        if paragraph.strip()
    ]
    if not paragraphs and body_text:
        paragraphs = [body_text]

    return EmailView(
        greeting=greeting,
        paragraphs=paragraphs,
        sign_off=sign_off or "Best regards,",
        signature=signature or sender,
        attachments=[str(item) for item in (attachments or []) if str(item).strip()],
        to_label=f"{company} hiring team" if company else "Hiring team",
    )


def _clean(body: str) -> str:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def _remove_attachments(text: str) -> str:
    text = _ATTACHMENTS_LINE.sub("", text)
    text = _ATTACHMENTS_TAIL.sub("", text)
    return text.strip()


def _phrase(value: str) -> str:
    value = " ".join(str(value or "").split())
    return value[:1].upper() + value[1:] + "," if value else ""
