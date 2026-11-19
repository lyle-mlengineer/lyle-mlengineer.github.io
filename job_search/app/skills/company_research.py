"""Skill 3 — public company research with citable evidence."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from ..jobs.prompts import research_block, system_prompt, untrusted
from ..providers.llm.base import ChatMessage
from ..providers.search.base import BudgetExceeded, SearchProviderError
from .base import Skill, SkillContext, job_block
from .text import items, text

logger = logging.getLogger("skipper.skills.research")


class CompanyResearchSkill(Skill):
    name = "company_research"
    tier = "large"
    output_kind = "company_research"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 4_000

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["summary", "sources", "open_questions"],
            "properties": {
                "summary": {"type": "string", "max_len": 900},
                "industry": {"type": "string", "max_len": 120},
                "size": {"type": "string", "max_len": 60},
                "founded": {"type": "string", "max_len": 20},
                "hq": {"type": "string", "max_len": 140},
                "products": {"type": "array", "items": {"type": "string", "max_len": 220}},
                "tech_stack": {"type": "array", "items": {"type": "string", "max_len": 80}},
                "culture": {"type": "array", "items": {"type": "string", "max_len": 220}},
                "news": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["headline", "url"],
                        "properties": {
                            "headline": {"type": "string", "max_len": 220},
                            "date": {"type": "string", "max_len": 40},
                            "url": {"type": "string", "max_len": 1000},
                        },
                    },
                },
                "interview_style": {"type": "string", "max_len": 500},
                "talking_points": {"type": "array", "items": {"type": "string", "max_len": 260}},
                "open_questions": {"type": "array", "items": {"type": "string", "max_len": 260}},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "url"],
                        "properties": {
                            "title": {"type": "string", "max_len": 220},
                            "url": {"type": "string", "max_len": 1000},
                            "grade": {"type": "string", "max_len": 20},
                        },
                    },
                },
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        evidence, _sources = gather_evidence(ctx)
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "company_research",
                    "Research the company for an applicant. Assert only what <research> supports. "
                    "Keep source URLs exactly as given. If something is missing, put it in open_questions "
                    "instead of guessing. News items need a URL from the evidence.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=7000)
                + "\n\n"
                + untrusted("research", evidence or "No search results were available.", limit=12000)
                + "\n\n"
                + research_block(ctx, limit=2500)
                + "\n\nWrite the company brief JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        _evidence, allowed = gather_evidence(ctx)
        sources = []
        for row in payload.get("sources") or []:
            if not isinstance(row, dict):
                continue
            url = _url(row.get("url"))
            if not url or not _allowed(url, allowed):
                continue
            sources.append(
                {
                    "title": text(row.get("title"), 220) or _host(url),
                    "url": url,
                    "grade": "page" if url in allowed.get("fetched", set()) else "snippet",
                }
            )
        sources = _dedupe(sources, "url")[:8]
        news = []
        for row in payload.get("news") or []:
            if not isinstance(row, dict):
                continue
            url = _url(row.get("url"))
            if not url or not _allowed(url, allowed):
                continue
            news.append(
                {"headline": text(row.get("headline"), 220), "date": text(row.get("date"), 40), "url": url}
            )
        return {
            "summary": text(payload.get("summary"), 900),
            "industry": text(payload.get("industry"), 120),
            "size": text(payload.get("size"), 60),
            "founded": text(payload.get("founded"), 20),
            "hq": text(payload.get("hq"), 140),
            "products": items(payload.get("products"), 8, item_limit=220),
            "tech_stack": items(payload.get("tech_stack"), 12, item_limit=80),
            "culture": items(payload.get("culture"), 6, item_limit=220),
            "news": _dedupe(news, "url")[:5],
            "interview_style": text(payload.get("interview_style"), 500),
            "talking_points": items(payload.get("talking_points"), 8, item_limit=260),
            "open_questions": items(payload.get("open_questions"), 8, item_limit=260),
            "sources": sources,
            "queries": allowed.get("queries", []),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# {company} — company brief", "", f"Prepared for **{ctx.job.title}**.", ""]
        if payload["summary"]:
            lines += [payload["summary"], ""]
        facts = [
            ("Industry", payload["industry"]),
            ("Size", payload["size"]),
            ("Founded", payload["founded"]),
            ("HQ", payload["hq"]),
        ]
        known = [f"- **{label}:** {value}" for label, value in facts if value]
        if known:
            lines += ["## At a glance", *known, ""]
        for title, key in (("Products", "products"), ("Tech stack", "tech_stack"), ("How they work", "culture")):
            if payload[key]:
                lines += [f"## {title}", *[f"- {item}" for item in payload[key]], ""]
        if payload["news"]:
            lines += ["## Recent news"]
            for item in payload["news"]:
                date = f" ({item['date']})" if item["date"] else ""
                lines.append(f"- [{item['headline']}]({item['url']}){date}")
            lines.append("")
        if payload["interview_style"]:
            lines += ["## Interview style", payload["interview_style"], ""]
        if payload["talking_points"]:
            lines += ["## Talking points", *[f"- {item}" for item in payload["talking_points"]], ""]
        if payload["open_questions"]:
            lines += ["## Worth asking", *[f"- {item}" for item in payload["open_questions"]], ""]
        if payload["sources"]:
            lines += ["## Sources"]
            for source in payload["sources"]:
                lines.append(f"- [{source['title']}]({source['url']}) — {source['grade']}")
        else:
            lines += ["## Sources", "- No public pages could be verified for this run."]
        return "\n".join(lines).strip() + "\n"


def gather_evidence(ctx: SkillContext) -> tuple[str, dict[str, Any]]:
    """Search up to four queries, fetch one page per query, keep URLs for citation checks."""
    allowed: dict[str, Any] = {"urls": set(), "fetched": set(), "queries": []}
    if ctx.search is None:
        return "", allowed
    extraction = ctx.prior.get("job_extraction") or {}
    company = ctx.company.name if ctx.company else str(extraction.get("company_name") or "")
    if not company:
        return "", allowed
    must = ", ".join((extraction.get("must_have") or [])[:5])
    queries = [
        f"{company} company overview",
        f"{company} engineering blog {must}",
        f"{company} recent news",
        f"{company} interview process engineers",
    ]
    blocks: list[str] = []
    fetched_count = 0
    for query in queries:
        allowed["queries"].append(query)
        try:
            results = ctx.search.search(query, limit=4)
        except (SearchProviderError, BudgetExceeded) as exc:
            logger.warning("research search failed for %s: %s", company, exc)
            continue
        for result in results:
            allowed["urls"].add(_norm(result.url))
        for result in results[:1]:
            block = f"RESULT: {result.title}\nURL: {result.url}\nSNIPPET: {result.snippet}\n"
            if fetched_count < 3 and ctx.fetcher is not None:
                try:
                    page = ctx.fetcher.fetch(result.url, respect_robots=True)
                    if page.ok:
                        allowed["fetched"].add(_norm(page.final_url))
                        allowed["urls"].add(_norm(page.final_url))
                        block += f"PAGE:\n{page.text[:2500]}\n"
                        fetched_count += 1
                except Exception as exc:  # fetch is best effort; snippet remains evidence
                    logger.info("research fetch skipped %s: %s", result.url, exc)
            blocks.append(block)
    return "\n\n".join(blocks)[:12_000], allowed


def _url(value: Any) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    return raw if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _norm(url: str) -> str:
    return _url(url).rstrip("/")


def _allowed(url: str, allowed: dict[str, Any]) -> bool:
    return _norm(url) in allowed["urls"] or _norm(url) in allowed["fetched"]


def _host(url: str) -> str:
    return urlparse(url).netloc[:220]


def _dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        if row[key] in seen:
            continue
        seen.add(row[key])
        out.append(row)
    return out
