"""Skill 4 — a tailored resume, grounded in the portfolio corpus.

The model chooses emphasis; this module owns the shape. Rendering is split out
(``app.documents``) so the same normalised resume feeds DOCX, PDF and tests.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..providers.llm.base import ChatMessage
from ..rag.grounding import check_numbers
from .base import GROUND_RULES, Skill, SkillContext, job_block
from .cv_templates import template_prompt

logger = logging.getLogger("skipper.skills.cv")

CORPUS_FILES = ("profile.md", "experience.md", "skills.md", "projects.md", "writing.md")
MAX_BULLET_CHARS = 260
MAX_BULLETS = 5


class CVWritingSkill(Skill):
    name = "cv_writing"
    tier = "large"
    output_kind = "cv"
    requires = ("job_extraction",)
    weight = 3.0
    max_tokens = 5_500

    def schema(self) -> dict[str, Any]:
        bullet = {"type": "string", "min_len": 20, "max_len": MAX_BULLET_CHARS}
        return {
            "type": "object",
            "required": ["headline", "summary", "skill_groups", "experience", "projects", "education"],
            "properties": {
                "headline": {"type": "string", "min_len": 8, "max_len": 120},
                "summary": {"type": "string", "min_len": 120, "max_len": 900},
                "skill_groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "items"],
                        "properties": {
                            "name": {"type": "string", "max_len": 60},
                            "items": {"type": "array", "items": {"type": "string", "max_len": 100}},
                        },
                    },
                },
                "tech_groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "items"],
                        "properties": {
                            "name": {"type": "string", "max_len": 60},
                            "items": {"type": "array", "items": {"type": "string", "max_len": 120}},
                        },
                    },
                },
                "experience": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "company", "dates", "bullets"],
                        "properties": {
                            "title": {"type": "string", "max_len": 120},
                            "company": {"type": "string", "max_len": 120},
                            "dates": {"type": "string", "max_len": 40},
                            "location": {"type": "string", "max_len": 80},
                            "bullets": {"type": "array", "items": bullet},
                        },
                    },
                },
                "projects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "bullets"],
                        "properties": {
                            "name": {"type": "string", "max_len": 120},
                            "meta": {"type": "string", "max_len": 160},
                            "bullets": {"type": "array", "items": bullet},
                            "links": {"type": "array", "items": {"type": "string", "max_len": 220}},
                        },
                    },
                },
                "education": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["credential", "institution", "dates"],
                        "properties": {
                            "credential": {"type": "string", "max_len": 160},
                            "institution": {"type": "string", "max_len": 160},
                            "dates": {"type": "string", "max_len": 40},
                        },
                    },
                },
                "certifications": {"type": "string", "max_len": 300},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        extraction = ctx.prior.get("job_extraction", {})
        role = ctx.job.title
        company = ctx.company.name if ctx.company else "the company"
        template = template_prompt(ctx.settings.portfolio_dir, role)
        template_block = (
            "\n\n<cv_template>\n"
            + "This is Lyle's own portfolio CV for the closest role. Reproduce its structure,\n"
            + "section names, competency naming, tone and metric-bearing bullets; tailor the\n"
            + "content to the posting by selecting, reordering and rewriting. Prefer its wording\n"
            + "and numbers where they are supported by <portfolio>. Never copy a claim that is\n"
            + "not in <portfolio>, and never add a skill or metric the portfolio cannot defend.\n"
            + template
            + "\n</cv_template>"
        )
        return [
            ChatMessage(
                "system",
                GROUND_RULES
                + "\nSKILL: cv_writing\n"
                + "Write Lyle's resume for this exact job. Tailor emphasis, never facts.\n"
                + "This is a competitive application, not a biography: every line must answer a line in the posting.\n"
                + "- ATS-safe order: headline, summary, skills, experience, projects, education, certifications.\n"
                + "- Headline: the target role plus the two strongest matching domains (for example\n"
                + "  'Machine Learning Engineer — Speech, Multilingual ASR').\n"
                + "- Summary: 3 sentences, 80-110 words. Sentence one names the role and years/domain.\n"
                + "  Sentence two is the strongest quantified proof. Sentence three names the constraints\n"
                + "  Lyle has shipped under. Mirror the posting's nouns exactly; no adjectives doing the work.\n"
                + "- Keep roles in reverse-chronological order and never change dates. Use 3-4 bullets for\n"
                + "  relevant roles, 2 for older ones. Every bullet is one line, starts with a strong\n"
                + "  past-tense verb, and has the form: action -> mechanism -> outcome.\n"
                + "- Put the bullet that answers the posting's first must-have first in each role.\n"
                + "- Skills: at most four groups, six items each, ordered by what the posting asks for. Use the\n"
                + "  posting's exact keywords where they are truthful (ATS matching), not synonyms.\n"
                + "- Projects: at most three, only ones that prove a requirement. Name the constraint and the\n"
                + "  evaluation method, not just the stack.\n"
                + "- Keep quantified claims exactly as they appear in <portfolio>. Drop a number you cannot support.\n"
                + "- No brackets, no placeholders, no referees, no photo, no adjective stacks.\n",
            ),
            ChatMessage(
                "user",
                job_block(ctx)
                + "\n\n<extraction>\n"
                + json.dumps(extraction, ensure_ascii=False, indent=2)[:5000]
                + "\n</extraction>\n\n<portfolio>\n"
                + _corpus(ctx.settings.portfolio_dir)[:16_000]
                + "\n</portfolio>\n\n"
                + template_block
                + "\n\n<must_have>\n"
                + "\n".join(f"- {item}" for item in (extraction.get("must_have") or [])[:12])
                + "\n</must_have>\n\n"
                + f"Target: {role} at {company}. Return the resume JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        corpus = _corpus(ctx.settings.portfolio_dir)
        resume = {
            "headline": _text(payload.get("headline"), 120).upper(),
            "summary": _scrub(_text(payload.get("summary"), 900), corpus),
            "skill_groups": _skill_groups(payload.get("skill_groups")),
            "tech_groups": _skill_groups(payload.get("tech_groups")),
            "experience": _experience(payload.get("experience"), corpus),
            "projects": _projects(payload.get("projects"), corpus),
            "education": _education(payload.get("education")),
            "certifications": _text(payload.get("certifications"), 300),
        }
        return resume


def _corpus(portfolio_dir: Path) -> str:
    parts: list[str] = []
    for name in CORPUS_FILES:
        path = Path(portfolio_dir) / name
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n\n".join(parts)


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _list(value: Any, limit: int, *, item_limit: int = 400) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _text(item, item_limit)
        if text and text not in out:
            out.append(text)
    return out[:limit]


def _skill_groups(value: Any) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return groups
    for group in value:
        if not isinstance(group, dict):
            continue
        name = _text(group.get("name"), 60)
        items = _list(group.get("items"), 8, item_limit=100)
        if name and items:
            groups.append({"name": name, "items": items})
    return groups[:4]


def _experience(value: Any, corpus: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return jobs
    for row in value:
        if not isinstance(row, dict):
            continue
        title = _text(row.get("title"), 120)
        company = _text(row.get("company"), 120)
        dates = _dates(row.get("dates"))
        bullets = [_scrub(text, corpus) for text in _list(row.get("bullets"), MAX_BULLETS, item_limit=MAX_BULLET_CHARS)]
        if title and company and bullets:
            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "dates": dates or "Dates not stated",
                    "location": _text(row.get("location"), 80),
                    "bullets": bullets,
                }
            )
    return jobs[:5]


def _projects(value: Any, corpus: str) -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return projects
    for row in value:
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name"), 120)
        bullets = [_scrub(text, corpus) for text in _list(row.get("bullets"), 3, item_limit=MAX_BULLET_CHARS)]
        if name and bullets:
            projects.append(
                {
                    "name": name,
                    "meta": _text(row.get("meta"), 160),
                    "bullets": bullets,
                    "links": _links(row.get("links")),
                }
            )
    return projects[:3]


def _links(value: Any) -> list[str]:
    links: list[str] = []
    if not isinstance(value, list):
        return links
    for item in value:
        url = _text(item, 220)
        if url.startswith(("https://", "http://")) and url not in links:
            links.append(url)
    return links[:2]


def _education(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for row in value:
        if not isinstance(row, dict):
            continue
        credential = _text(row.get("credential"), 160)
        institution = _text(row.get("institution"), 160)
        if credential and institution:
            rows.append(
                {
                    "credential": credential,
                    "institution": institution,
                    "dates": _dates(row.get("dates")) or "",
                }
            )
    return rows[:3]


def _dates(value: Any) -> str:
    text = _text(value, 40)
    if not text:
        return ""
    text = re.sub(r"\s*[-–—]\s*", " – ", text)
    text = re.sub(r"\bpresent\b", "Present", text, flags=re.IGNORECASE)
    return text


def _scrub(text: str, corpus: str) -> str:
    """Replace numeric claims the portfolio cannot support, then re-check."""
    unsupported = check_numbers(text, corpus)
    if not unsupported:
        return text
    logger.warning("cv claim dropped unsupported numbers: %s", unsupported)
    for token in sorted(set(unsupported), key=len, reverse=True):
        text = text.replace(token, "measurably")
    text = re.sub(r"\bmeasurably\s+measurably\b", "measurably", text, flags=re.IGNORECASE)
    text = re.sub(r"(measurably)(?:\s+measurably)+", r"\1", text)
    return " ".join(text.split())
