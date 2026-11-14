import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.profile import (
    Offering,
    PageRole,
    SiteProfile,
    Understanding,
    ValueProposition,
)

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ALLOWED_ROLES = {
    "home",
    "about",
    "work",
    "services",
    "pricing",
    "contact",
    "blog",
    "other",
}

SYSTEM_PROMPT = """You read a company or personal website and explain what it is for.
Return a single JSON object with exactly these keys:

{
  "value_proposition": {"text": "...", "source_id": "b123"} | null,
  "audience": "..." | null,
  "tone": ["technical", "warm"],
  "page_roles": [{"url": "https://...", "role": "work"}],
  "offerings": [{"title": "...", "summary": "...", "source_ids": ["b123"]}]
}

Rules:
- Use only the supplied blocks. Every claim must point at a source_id from that page.
- Never invent numbers, names, client counts, dates or quotes. If a number is
  not in the supplied text, do not write it.
- value_proposition is at most 240 characters, in the site's own voice.
- audience is who the site is for, at most 120 characters.
- tone is 1-5 lowercase adjectives.
- offerings: at most 6, each with a title from a heading and supporting source_ids.
- page_roles covers only URLs supplied to you.
- If you cannot support a field from the text, return null or an empty list.
"""


class LLMError(RuntimeError):
    pass


class LLMClient:
    """Minimal OpenAI-compatible chat client returning parsed JSON."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        settings = get_settings()
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        self._http = http

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("No LLM API key configured")

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        client = self._http or httpx.Client(timeout=self.timeout)
        try:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 400:
                # Some compatible providers reject response_format.
                payload.pop("response_format", None)
                response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        finally:
            if self._http is None:
                client.close()

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("LLM response did not contain a message") from exc

        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        if not isinstance(content, str):
            raise LLMError("LLM message content was not text")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("LLM did not return valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMError("LLM JSON was not an object")
        return parsed


def compressed_site(profile: SiteProfile) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for page in profile.pages[:12]:
        pages.append(
            {
                "id": page.id,
                "url": page.url,
                "headings": [
                    {"level": heading.level, "text": heading.text, "source_id": heading.block_id}
                    for heading in page.headings[:20]
                ],
                "blocks": [
                    {"source_id": block.id, "kind": block.kind, "text": block.text[:320]}
                    for block in page.blocks[:70]
                ],
            }
        )
    return {
        "url": profile.url,
        "title": profile.title,
        "brand": {
            "colors": [color.hex for color in profile.brand.colors[:5]],
            "fonts": [font.family for font in profile.brand.fonts[:4]],
        },
        "pages": pages,
    }


def build_messages(profile: SiteProfile) -> tuple[str, str]:
    return SYSTEM_PROMPT, json.dumps(compressed_site(profile), ensure_ascii=False, indent=1)


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMBER.finditer(text)}


def _supported(text: str, corpus: str) -> bool:
    return _numbers(text) <= _numbers(corpus)


def _clean_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def parse_understanding(payload: dict[str, Any], profile: SiteProfile) -> Understanding | None:
    """Validate LLM output against the crawled blocks before accepting it."""
    blocks = {block.id: block.text for page in profile.pages for block in page.blocks}
    corpus = "\n".join(blocks.values()) + "\n" + profile.title
    page_urls = {page.url.rstrip("/"): page.url for page in profile.pages}
    result = Understanding(ai_generated=True)

    value = payload.get("value_proposition")
    if isinstance(value, dict):
        text = _clean_text(value.get("text"), 240)
        source_id = value.get("source_id")
        if isinstance(source_id, str) and source_id not in blocks:
            source_id = None
        if text and _supported(text, corpus):
            result.value_proposition = ValueProposition(text=text, source_id=source_id)

    audience = _clean_text(payload.get("audience"), 120)
    if audience and _supported(audience, corpus):
        result.audience = audience

    tone = payload.get("tone")
    if isinstance(tone, list):
        result.tone = [
            item
            for item in (_clean_text(entry, 24) for entry in tone)
            if item and len(item) <= 24
        ][:5]

    roles = payload.get("page_roles")
    if isinstance(roles, list):
        for entry in roles[:12]:
            if not isinstance(entry, dict):
                continue
            url = _clean_text(entry.get("url"), 2048)
            role = _clean_text(entry.get("role"), 24)
            if not url or not role or role.lower() not in _ALLOWED_ROLES:
                continue
            canonical = page_urls.get(url.rstrip("/"))
            if canonical:
                result.page_roles.append(PageRole(url=canonical, role=role.lower()))

    offerings = payload.get("offerings")
    if isinstance(offerings, list):
        seen: set[str] = set()
        for entry in offerings[:6]:
            if not isinstance(entry, dict):
                continue
            title = _clean_text(entry.get("title"), 90)
            summary = _clean_text(entry.get("summary"), 220)
            raw_ids = entry.get("source_ids")
            source_ids = (
                [item for item in raw_ids if isinstance(item, str) and item in blocks][:6]
                if isinstance(raw_ids, list)
                else []
            )
            if not title or not source_ids or title.lower() in seen:
                continue
            if summary and not _supported(summary, corpus):
                summary = None
            seen.add(title.lower())
            result.offerings.append(
                Offering(
                    title=title,
                    summary=summary,
                    source_ids=source_ids,
                )
            )

    if result.value_proposition is None and not result.offerings and not result.page_roles:
        return None
    return result
