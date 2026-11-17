"""Deterministic pre-pass: find grounded candidates before any model runs."""

import re
from datetime import date

from app.pipeline.extract.candidates import CandidateSet, QuoteCandidate, slug
from app.pipeline.extract.ground import ground_fact, numbers
from app.pipeline.understand.heuristics import heuristic_understanding
from app.schemas.content import Fact, Offering, Project
from app.schemas.profile import SiteProfile, Understanding

_PERCENT = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*%")
_TIME = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?)\s*(ms|milliseconds?|seconds?|secs?|minutes?|mins?)\b",
    re.IGNORECASE,
)
_COUNT = re.compile(
    r"\b(\d[\d,]*)\s+((?:[a-z][a-z-]*\s+){0,2}"
    r"(?:voices?|creators?|users?|customers?|projects?|models?|clients?))\b",
    re.IGNORECASE,
)
_SPELLED = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"((?:[a-z][a-z-]*\s+){0,2}"
    r"(?:voices?|creators?|users?|customers?|projects?|models?|clients?))\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_COMPARISON = re.compile(r"\b(?:down|up)\s+from\b", re.IGNORECASE)
_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)[a-z]*\s+(\d{4})\b",
    re.IGNORECASE,
)
_ATTRIBUTION = re.compile(
    r"^([A-Z][\w'.?-]+(?:\s+[A-Z][\w'.?-]+){1,3})\s*,\s*(.+)$"
)
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_CLIENT = re.compile(
    r"\b(?:clients?|customers?|trusted by|worked with)\s*"
    r"(?:include|includes|:)?\s*"
    r"([A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3})"
)
_QUOTE_MARKS = "\"'?\u201c\u201d\u2018\u2019"
_METRIC_KINDS = {"p", "li", "td", "dd", "figcaption"}
_SKIP_PROJECT_HEADINGS = {
    "work",
    "selected work",
    "projects",
    "case studies",
    "experience",
    "what i do",
}
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
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def ensure_understanding(profile: SiteProfile) -> Understanding:
    reading = profile.understanding
    if reading.value_proposition or reading.offerings or reading.page_roles:
        return reading
    return heuristic_understanding(profile)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(text) if part.strip()]


def _as_of(sentence: str) -> str | None:
    match = _MONTH.search(sentence)
    if not match:
        return None
    return f"{match.group(2)}-{_MONTHS[match.group(1).lower()]:02d}"


def _context_label(sentence: str, start: int, words: int = 5) -> str:
    prefix = re.sub(r"[^\w\s%.-]", " ", sentence[:start])
    parts = prefix.split()
    label = " ".join(parts[-words:]).strip(" -")
    return label or "value"


def _add_fact(
    candidates: CandidateSet,
    *,
    key: str,
    value: str,
    label: str,
    unit: str | None,
    source: str,
    source_id: str,
    source_quote: str,
    source_text: str,
    retrieved_at: date,
    as_of: str | None = None,
    permission: str | None = None,
) -> Fact | None:
    value = value[:600]
    source_quote = source_quote[:2000]
    existing = next((fact for fact in candidates.facts if fact.key == key), None)
    if existing is not None:
        if existing.value == value and existing.source_id == source_id:
            return existing
        candidates.conflicts.append(key)
        candidates.reject(
            key=key,
            value=value,
            unit=unit,
            source_id=source_id,
            source_quote=source_quote,
            reason="conflict",
        )
        return None

    accepted, reason = ground_fact(value, source_quote, source_text)
    if not accepted:
        candidates.reject(
            key=key,
            value=value,
            unit=unit,
            source_id=source_id,
            source_quote=source_quote,
            reason=reason or "invalid",
        )
        return None

    fact = Fact(
        id=f"f_{len(candidates.facts) + 1:02d}",
        key=key,
        value=value[:600],
        unit=unit,
        label=label,
        as_of=as_of,
        source_type="site",
        source=source,
        source_id=source_id,
        source_quote=source_quote[:2000],
        confidence=0.99,
        tier="A",
        retrieved_at=retrieved_at,
        permission=permission,
    )
    candidates.facts.append(fact)
    return fact


def _percent_facts(
    candidates: CandidateSet,
    *,
    sentence: str,
    source: str,
    source_id: str,
    source_text: str,
    retrieved_at: date,
) -> None:
    matches = list(_PERCENT.finditer(sentence))
    if not matches:
        return
    comparing = bool(_COMPARISON.search(sentence))
    as_of = _as_of(sentence)
    lowered = sentence.lower()

    for index, match in enumerate(matches):
        if comparing and index > 0:
            continue
        value = match.group(1).replace(",", "")
        if "word error rate" in lowered or re.search(r"\bwer\b", lowered):
            key, label, unit = "asr.wer", "word error rate", "% WER"
        elif "retention" in lowered:
            label = "week-4 retention" if "week-4" in lowered else "retention"
            key, unit = "product.retention", "%"
        elif "accuracy" in lowered:
            key, label, unit = "model.accuracy", "accuracy", "%"
        elif "faster" in lowered:
            key, label, unit = "performance.speed", "faster than baseline", "% faster"
        else:
            label = _context_label(sentence, match.start())
            key, unit = f"metric.{slug(label)}", "%"
        _add_fact(
            candidates,
            key=key,
            value=value,
            label=label[:160],
            unit=unit,
            source=source,
            source_id=source_id,
            source_quote=sentence,
            source_text=source_text,
            retrieved_at=retrieved_at,
            as_of=as_of,
        )


def _time_facts(
    candidates: CandidateSet,
    *,
    sentence: str,
    source: str,
    source_id: str,
    source_text: str,
    retrieved_at: date,
) -> None:
    lowered = sentence.lower()
    as_of = _as_of(sentence)
    for match in _TIME.finditer(sentence):
        value = match.group(1).replace(",", "")
        raw = match.group(2).lower()
        if raw.startswith("ms") or raw.startswith("milli"):
            key, label, unit = "system.latency", "latency", "ms"
        elif raw.startswith("sec"):
            if any(word in lowered for word in ("render", "script", "skit", "video", "generate")):
                key, label, unit = "media.render_seconds", "render time", "s"
            else:
                key, label, unit = "metric.duration", "duration", "s"
        else:
            key, label, unit = "metric.duration", "duration", "min"
        _add_fact(
            candidates,
            key=key,
            value=value,
            label=label,
            unit=unit,
            source=source,
            source_id=source_id,
            source_quote=sentence,
            source_text=source_text,
            retrieved_at=retrieved_at,
            as_of=as_of,
        )


def _count_key(label: str) -> tuple[str, str]:
    noun = label.split()[-1].lower().rstrip("s")
    mapping = {
        "voice": "asr.voices",
        "creator": "product.creators",
        "user": "product.users",
        "customer": "product.customers",
        "client": "proof.clients",
        "project": "work.projects",
        "model": "model.models",
    }
    return mapping.get(noun, f"metric.{slug(label)}"), label.lower()


def _count_facts(
    candidates: CandidateSet,
    *,
    sentence: str,
    source: str,
    source_id: str,
    source_text: str,
    retrieved_at: date,
) -> None:
    as_of = _as_of(sentence)
    found: list[tuple[str, str]] = []
    for match in _COUNT.finditer(sentence):
        found.append((match.group(1), match.group(2)))
    for match in _SPELLED.finditer(sentence):
        found.append((_NUMBER_WORDS[match.group(1).lower()], match.group(2)))

    for value, label in found:
        key, clean_label = _count_key(label)
        _add_fact(
            candidates,
            key=key,
            value=value,
            label=clean_label[:160],
            unit=None,
            source=source,
            source_id=source_id,
            source_quote=sentence,
            source_text=source_text,
            retrieved_at=retrieved_at,
            as_of=as_of,
        )


def _metric_candidates(
    profile: SiteProfile,
    candidates: CandidateSet,
    retrieved_at: date,
) -> None:
    for page in profile.pages:
        for block in page.blocks:
            if block.kind not in _METRIC_KINDS:
                continue
            for sentence in _sentences(block.text):
                _percent_facts(
                    candidates,
                    sentence=sentence,
                    source=page.url,
                    source_id=block.id,
                    source_text=block.text,
                    retrieved_at=retrieved_at,
                )
                _time_facts(
                    candidates,
                    sentence=sentence,
                    source=page.url,
                    source_id=block.id,
                    source_text=block.text,
                    retrieved_at=retrieved_at,
                )
                _count_facts(
                    candidates,
                    sentence=sentence,
                    source=page.url,
                    source_id=block.id,
                    source_text=block.text,
                    retrieved_at=retrieved_at,
                )


def _strip_quotes(text: str) -> str:
    value = text.strip()
    changed = True
    while changed and value:
        changed = False
        if value[0] in _QUOTE_MARKS:
            value = value[1:].lstrip()
            changed = True
        if value and value[-1] in _QUOTE_MARKS:
            value = value[:-1].rstrip()
            changed = True
    return value


def _parse_attribution(text: str) -> tuple[str | None, str | None]:
    cleaned = re.sub(r"\s+", " ", text).strip().rstrip(".")
    match = _ATTRIBUTION.match(cleaned)
    if not match:
        return None, None
    name = match.group(1).strip()
    role = match.group(2).strip(" -\u2013\u2014")
    return name, role or None


def _quote_candidates(
    profile: SiteProfile,
    candidates: CandidateSet,
    retrieved_at: date,
) -> None:
    for page in profile.pages:
        blocks = page.blocks
        for index, block in enumerate(blocks):
            if block.kind != "blockquote":
                continue
            text = _strip_quotes(block.text)
            if len(text) < 20 or len(text) > 600:
                continue
            attribution: str | None = None
            role: str | None = None
            for candidate in blocks[index + 1 : index + 3]:
                if candidate.kind not in {"figcaption", "p"} or len(candidate.text) > 180:
                    continue
                name, found_role = _parse_attribution(candidate.text)
                if name:
                    attribution, role = name, found_role
                    break
            fact = _add_fact(
                candidates,
                key="proof.quote",
                value=text,
                label="client quote",
                unit=None,
                source=page.url,
                source_id=block.id,
                source_quote=text,
                source_text=block.text,
                retrieved_at=retrieved_at,
                permission="published_on_site",
            )
            if fact is not None:
                candidates.quote = QuoteCandidate(
                    fact=fact,
                    attribution=attribution,
                    role=role,
                )
            return


def _is_work_page(page_id: str, url: str) -> bool:
    return page_id.split("-")[0] == "work" or "/work" in url


def _metric_for_text(text: str, facts: list[Fact]) -> str | None:
    wanted = numbers(text)
    if not wanted:
        return None
    matches = [
        fact
        for fact in facts
        if fact.key != "proof.quote" and numbers(fact.value) & wanted
    ]
    return matches[0].id if len(matches) == 1 else None


def _project_candidates(
    profile: SiteProfile,
    candidates: CandidateSet,
) -> None:
    seen: set[str] = set()
    for page in profile.pages:
        if not _is_work_page(page.id, page.url):
            continue
        blocks = page.blocks
        for index, block in enumerate(blocks):
            if block.kind != "heading" or len(block.text) > 100:
                continue
            title = block.text.strip()
            if title.lower().strip(" :") in _SKIP_PROJECT_HEADINGS:
                continue
            blurb = ""
            for candidate in blocks[index + 1 : index + 4]:
                if candidate.kind == "heading":
                    break
                if candidate.kind in {"p", "li"} and len(candidate.text) >= 12:
                    blurb = _sentences(candidate.text)[0][:240]
                    break
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.projects.append(
                Project(
                    name=title[:100],
                    blurb=blurb,
                    badge_fact_id=_metric_for_text(f"{title} {blurb}", candidates.facts),
                    status="shipped",
                )
            )
            if len(candidates.projects) >= 8:
                return


def _offering_candidates(
    profile: SiteProfile,
    candidates: CandidateSet,
) -> None:
    reading = ensure_understanding(profile)
    project_names = {project.name.lower() for project in candidates.projects}
    person_name = (profile.entities.person.name or "").lower()
    seen: set[str] = set()
    for item in reading.offerings:
        title = item.title.strip()
        if not title or title.lower() in seen or title.lower() in project_names:
            continue
        if person_name and title.lower() == person_name:
            continue
        one_liner = (item.summary or title).strip()
        seen.add(title.lower())
        candidates.offerings.append(
            Offering(
                key=f"offer.{slug(title)}",
                title=title[:120],
                one_liner=one_liner[:320],
                metric_fact_id=_metric_for_text(f"{title} {one_liner}", candidates.facts),
                tools=[],
            )
        )
        if len(candidates.offerings) >= 4:
            return


def _add_signal(signals: dict[str, list[str]], key: str, value: str) -> None:
    bucket = signals.setdefault(key, [])
    if value and value not in bucket:
        bucket.append(value)


def _signal_candidates(
    profile: SiteProfile,
    candidates: CandidateSet,
) -> None:
    """Collect contact, date and client signals for the resolver ladder."""
    for page in profile.pages:
        for block in page.blocks:
            for email in _EMAIL.findall(block.text):
                _add_signal(candidates.signals, "emails", email.lower())
            for phone in _PHONE.findall(block.text):
                digits = re.sub(r"\D", "", phone)
                if 8 <= len(digits) <= 15:
                    _add_signal(candidates.signals, "phones", re.sub(r"\s+", " ", phone).strip())
            for match in _MONTH.finditer(block.text):
                _add_signal(
                    candidates.signals,
                    "dates",
                    f"{match.group(2)}-{_MONTHS[match.group(1).lower()]:02d}",
                )
            for match in _CLIENT.finditer(block.text):
                _add_signal(candidates.signals, "clients", match.group(1).strip())

    if candidates.quote is not None and candidates.quote.role:
        role = candidates.quote.role
        for separator in ("\u2014", "\u2013", " - ", " at "):
            if separator in role:
                client = role.split(separator)[-1].strip(" .")
                if client:
                    _add_signal(candidates.signals, "clients", client)
                break


def deterministic_candidates(
    profile: SiteProfile,
    retrieved_at: date,
) -> CandidateSet:
    candidates = CandidateSet()
    _metric_candidates(profile, candidates, retrieved_at)
    _quote_candidates(profile, candidates, retrieved_at)
    _project_candidates(profile, candidates)
    _offering_candidates(profile, candidates)
    _signal_candidates(profile, candidates)
    return candidates


def split_sentences(text: str) -> list[str]:
    """Public sentence splitter for document extraction."""
    return _sentences(text)


def parse_attribution(text: str) -> tuple[str | None, str | None]:
    """Public attribution parser for document quotes."""
    return _parse_attribution(text)


def metric_facts_for_text(
    text: str,
    *,
    source: str,
    source_id: str,
    retrieved_at: date,
) -> list[Fact]:
    """Find grounded percent, duration and count facts in one chunk.

    Document extraction reuses the same deterministic matchers as the site pass,
    so a metric read from a deck is grounded by exactly the same rules.
    """
    candidates = CandidateSet()
    for sentence in _sentences(text):
        _percent_facts(
            candidates,
            sentence=sentence,
            source=source,
            source_id=source_id,
            source_text=text,
            retrieved_at=retrieved_at,
        )
        _time_facts(
            candidates,
            sentence=sentence,
            source=source,
            source_id=source_id,
            source_text=text,
            retrieved_at=retrieved_at,
        )
        _count_facts(
            candidates,
            sentence=sentence,
            source=source,
            source_id=source_id,
            source_text=text,
            retrieved_at=retrieved_at,
        )
    return candidates.facts

