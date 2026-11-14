import re

from app.schemas.profile import (
    Offering,
    Page,
    PageRole,
    SiteProfile,
    Understanding,
    ValueProposition,
)

_BOILERPLATE = (
    "cookie",
    "privacy policy",
    "terms of service",
    "all rights reserved",
    "skip to content",
    "©",
)
_GENERIC_HEADINGS = {
    "about",
    "about me",
    "work",
    "projects",
    "selected work",
    "portfolio",
    "services",
    "pricing",
    "contact",
    "get in touch",
    "testimonials",
    "clients",
    "experience",
    "education",
    "blog",
    "writing",
}
_ROLE_MAP = {
    "home": "home",
    "about": "about",
    "work": "work",
    "projects": "work",
    "portfolio": "work",
    "services": "services",
    "pricing": "pricing",
    "contact": "contact",
    "blog": "blog",
    "writing": "blog",
}
_AUDIENCE = re.compile(r"(?:for|built for|helping|serving)\s+([a-z][a-z0-9 &,'/-]{3,50})")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _home(pages: list[Page]) -> Page | None:
    return next((page for page in pages if page.id == "home"), pages[0] if pages else None)


def _first_sentence(text: str, limit: int = 220) -> str:
    parts = _SENTENCE_END.split(text.strip(), maxsplit=1)
    value = parts[0] if parts else text
    if len(value) > limit:
        value = value[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return value


def _is_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BOILERPLATE)


def _value_proposition(page: Page | None) -> ValueProposition | None:
    if page is None:
        return None
    fallback: tuple[str, str] | None = None
    for block in page.blocks:
        if block.kind not in {"p", "blockquote", "figcaption"}:
            continue
        text = block.text.strip()
        if len(text) < 45 or _is_boilerplate(text):
            continue
        if fallback is None and len(text) <= 320:
            fallback = (text, block.id)
        if 55 <= len(text) <= 240:
            return ValueProposition(text=text, source_id=block.id)
    if fallback:
        return ValueProposition(text=_first_sentence(fallback[0]), source_id=fallback[1])
    return None


def _audience(pages: list[Page]) -> str | None:
    for page in pages[:2]:
        for block in page.blocks:
            match = _AUDIENCE.search(block.text.lower())
            if match:
                value = match.group(1).strip(" .,;:")
                return value[:120]
    return None


def _tone(pages: list[Page]) -> list[str]:
    corpus = " ".join(block.text for page in pages for block in page.blocks).lower()
    tones: list[str] = []
    if any(word in corpus for word in ("machine learning", "model", "api", "pipeline", "data")):
        tones.append("technical")
    if any(word in corpus for word in ("shipped", "production", "deployed", "built")):
        tones.append("confident")
    if any(word in corpus for word in ("i help", "we help", "i build", "we build", "together")):
        tones.append("warm")
    if corpus:
        sentences = [part for part in _SENTENCE_END.split(corpus) if part.strip()]
        if sentences and len(corpus.split()) / len(sentences) < 15:
            tones.append("concise")
    return tones[:4] or ["clear"]


def _page_roles(pages: list[Page]) -> list[PageRole]:
    roles: list[PageRole] = []
    for page in pages:
        base = page.id.split("-")[0]
        roles.append(PageRole(url=page.url, role=_ROLE_MAP.get(base, "other")))
    return roles


def _offerings(pages: list[Page]) -> list[Offering]:
    offerings: list[Offering] = []
    seen: set[str] = set()
    for page in pages:
        blocks = page.blocks
        for index, block in enumerate(blocks):
            if block.kind != "heading":
                continue
            if len(block.text) > 90 or block.text.lower().strip(" :") in _GENERIC_HEADINGS:
                continue
            summary: str | None = None
            source_ids = [block.id]
            for candidate in blocks[index + 1 : index + 4]:
                if candidate.kind == "heading":
                    continue
                if len(candidate.text) >= 25 and not _is_boilerplate(candidate.text):
                    summary = _first_sentence(candidate.text, 200)
                    source_ids.append(candidate.id)
                break
            key = block.text.lower()
            if key in seen:
                continue
            seen.add(key)
            offerings.append(Offering(title=block.text, summary=summary, source_ids=source_ids))
            if len(offerings) >= 5:
                return offerings
    return offerings


def heuristic_understanding(profile: SiteProfile) -> Understanding:
    home = _home(profile.pages)
    return Understanding(
        value_proposition=_value_proposition(home),
        audience=_audience(profile.pages),
        tone=_tone(profile.pages),
        page_roles=_page_roles(profile.pages),
        offerings=_offerings(profile.pages),
        ai_generated=False,
    )
