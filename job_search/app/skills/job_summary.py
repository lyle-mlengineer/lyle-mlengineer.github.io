"""Skill 2 — the short brief a human can read before deciding to apply."""

from __future__ import annotations

import json
from typing import Any

from ..providers.llm.base import ChatMessage
from .base import GROUND_RULES, Skill, SkillContext, job_block


class JobSummarySkill(Skill):
    name = "job_summary"
    tier = "small"
    output_kind = "job_summary"
    requires = ("job_extraction",)
    weight = 1.0
    max_tokens = 2_400

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["one_liner", "what_you_do", "what_they_want", "why_it_matters"],
            "properties": {
                "one_liner": {"type": "string", "min_len": 8, "max_len": 300},
                "what_you_do": {"type": "array", "items": {"type": "string", "max_len": 300}},
                "what_they_want": {"type": "array", "items": {"type": "string", "max_len": 300}},
                "why_it_matters": {"type": "string", "min_len": 8, "max_len": 800},
                "fit_signals": {"type": "array", "items": {"type": "string", "max_len": 300}},
                "gaps": {"type": "array", "items": {"type": "string", "max_len": 300}},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        extraction = ctx.prior.get("job_extraction", {})
        return [
            ChatMessage(
                "system",
                GROUND_RULES
                + "\nSKILL: job_summary\n"
                + "Summarise the role for Lyle. Fit signals and gaps must follow from the extraction and "
                + "the posting, not from assumptions about his CV. If the posting does not state something, "
                + "leave it out.",
            ),
            ChatMessage(
                "user",
                job_block(ctx)
                + "\n\n<extraction>\n"
                + json.dumps(extraction, ensure_ascii=False, indent=2)[:8000]
                + "\n</extraction>",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        return {
            "one_liner": _text(payload.get("one_liner"), 300),
            "what_you_do": _list(payload.get("what_you_do")),
            "what_they_want": _list(payload.get("what_they_want")),
            "why_it_matters": _text(payload.get("why_it_matters"), 800),
            "fit_signals": _list(payload.get("fit_signals")),
            "gaps": _list(payload.get("gaps")),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [
            f"# {ctx.job.title} at {company}",
            "",
            payload["one_liner"],
            "",
            "## What you would do",
            *_bullets(payload["what_you_do"]),
            "",
            "## What they want",
            *_bullets(payload["what_they_want"]),
            "",
            "## Why it matters",
            payload["why_it_matters"],
        ]
        if payload["fit_signals"]:
            lines += ["", "## Fit signals", *_bullets(payload["fit_signals"])]
        if payload["gaps"]:
            lines += ["", "## Gaps to address", *_bullets(payload["gaps"])]
        return "\n".join(lines).strip() + "\n"


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_text(item, 300) for item in value) if text][:10]


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- Not stated in the posting."]
