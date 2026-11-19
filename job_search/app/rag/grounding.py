"""Mechanical honesty checks.

A prompt can say "never invent numbers"; this module can prove whether it
happened. Every numeric token in generated prose is compared with the numbers in
the retrieved portfolio text. Anything missing is reported so the skill can
rewrite the claim to a qualitative statement before an artifact is saved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(
    r"(?<![\w.])(?P<value>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(?P<unit>%|ms|s|GB|MB|KB|TB|hours?|voices?|users?|creators?|projects?|x|M)(?![A-Za-z]))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumberClaim:
    raw: str
    value: str
    unit: str | None


def _canonical(value: str) -> str:
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:  # pragma: no cover - regex only yields digits
        return value
    if number == number.to_integral():
        return str(int(number))
    return format(number.normalize(), "f")


def extract_numbers(text: str) -> list[NumberClaim]:
    claims: list[NumberClaim] = []
    for match in _NUMBER.finditer(text or ""):
        claims.append(
            NumberClaim(
                raw=match.group(0).strip(),
                value=_canonical(match.group("value")),
                unit=(match.group("unit") or "").lower() or None,
            )
        )
    return claims


def check_numbers(claim_text: str, corpus_text: str) -> list[str]:
    """Return numeric tokens in `claim_text` that the corpus cannot support."""
    supported = {claim.value for claim in extract_numbers(corpus_text)}
    return [claim.raw for claim in extract_numbers(claim_text) if claim.value not in supported]


def is_grounded(claim_text: str, corpus_text: str) -> bool:
    return not check_numbers(claim_text, corpus_text)


def grounding_report(claim_text: str, corpus_text: str) -> dict[str, list[str]]:
    unsupported = check_numbers(claim_text, corpus_text)
    return {"unsupported": unsupported, "checked": [claim.raw for claim in extract_numbers(claim_text)]}
