import re
import unicodedata
from difflib import SequenceMatcher

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[a-z0-9]+")
_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}


def normalise(text: str) -> str:
    """Normalise quotes, dashes and whitespace before comparing spans."""
    value = unicodedata.normalize("NFKC", text)
    value = (
        value.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: str) -> list[str]:
    return _WORD.findall(normalise(text).lower())


def quote_match_ratio(quote: str, source: str) -> float:
    """How well a quote is contained in a source span (0..1)."""
    quote_tokens = _tokens(quote)
    source_tokens = _tokens(source)
    if not quote_tokens or not source_tokens:
        return 0.0
    if len(quote_tokens) > len(source_tokens):
        return SequenceMatcher(None, quote_tokens, source_tokens).ratio()

    if _contains(source_tokens, quote_tokens):
        return 1.0

    best = 0.0
    for extra in (0, 1, 2):
        width = len(quote_tokens) + extra
        if width > len(source_tokens):
            continue
        for start in range(len(source_tokens) - width + 1):
            window = source_tokens[start : start + width]
            score = SequenceMatcher(None, quote_tokens, window).ratio()
            if score > best:
                best = score
            if best >= 0.99:
                return best
    return best


def _contains(haystack: list[str], needle: list[str]) -> bool:
    width = len(needle)
    return any(
        haystack[index : index + width] == needle
        for index in range(len(haystack) - width + 1)
    )


def quote_matches(quote: str, source: str, threshold: float = 0.92) -> bool:
    return quote_match_ratio(quote, source) >= threshold


def numbers(text: str) -> set[str]:
    found = {match.group(0).replace(",", "") for match in _NUMBER.finditer(text)}
    for match in _WORD.finditer(normalise(text).lower()):
        value = _NUMBER_WORDS.get(match.group(0))
        if value:
            found.add(value)
    return found


def number_mismatch_reason(value: str, source: str) -> str | None:
    """Return a reject reason when ``value`` is not grounded in ``source``."""
    wanted = numbers(value)
    available = numbers(source)
    if not wanted:
        return None
    if wanted <= available:
        return None
    for candidate in wanted - available:
        try:
            target = float(candidate)
        except ValueError:
            continue
        for reference in available:
            try:
                base = float(reference)
            except ValueError:
                continue
            if base <= 0 or target == base:
                continue
            if target == round(base) or abs(target - base) / base < 0.06:
                return "unsupported_rounding"
    return "number_mismatch"


def ground_fact(
    value: str,
    source_quote: str,
    source_text: str,
) -> tuple[bool, str | None]:
    """Validate a candidate against the block it cites.

    A fact is accepted only when the quote is present in the cited block and
    every number in the value appears in that quote.
    """
    if not source_quote.strip():
        return False, "no_source"
    if not quote_matches(source_quote, source_text):
        return False, "no_source"
    reason = number_mismatch_reason(value, source_quote)
    if reason:
        return False, reason
    return True, None


def ground_quote(quote: str, source_text: str) -> tuple[bool, str | None]:
    if not quote.strip():
        return False, "no_source"
    if not quote_matches(quote, source_text):
        return False, "no_source"
    return True, None
