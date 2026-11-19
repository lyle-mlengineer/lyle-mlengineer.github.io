"""Skill 5 — a 350-word cover letter that names the real company and role."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_words, drop_placeholders, items, strip_cliches, text, word_count


class CoverLetterSkill(Skill):
    name = "cover_letter"
    tier = "small"
    output_kind = "cover_letter"
    requires = ("job_extraction", "company_research")
    weight = 2.0
    max_tokens = 2_200

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["greeting", "paragraphs", "closing"],
            "properties": {
                "greeting": {"type": "string", "min_len": 3, "max_len": 120},
                "paragraphs": {"type": "array", "items": {"type": "string", "min_len": 60, "max_len": 700}},
                "closing": {"type": "string", "min_len": 3, "max_len": 120},
                "word_count": {"type": "integer"},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "cover_letter",
                    "Write a one-page cover letter for this role. Three or four paragraphs, at most 330 "
                    "words. Open with the role and the company, prove two or three claims from the "
                    "portfolio that the posting asks for, and close with a concrete next step. Use the "
                    "company research only for why this company. No letterhead, no address block.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx)
                + "\n\n"
                + research_block(ctx, limit=4000)
                + "\n\n"
                + portfolio_block(ctx, limit=7000)
                + "\n\nWrite the cover letter JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        greeting = strip_cliches(text(payload.get("greeting"), 120))
        closing = strip_cliches(text(payload.get("closing"), 120))
        paragraphs = [strip_cliches(value) for value in items(payload.get("paragraphs"), 5, item_limit=700)]
        paragraphs = drop_placeholders(paragraphs)
        allowed = 350 - word_count(greeting) - word_count(closing)
        kept: list[str] = []
        used = 0
        for paragraph in paragraphs:
            if used >= allowed:
                break
            remaining = allowed - used
            clipped = clip_words(paragraph, remaining)
            kept.append(clipped)
            used += word_count(clipped)
        return {
            "greeting": greeting,
            "paragraphs": kept,
            "closing": closing,
            "word_count": word_count(greeting) + used + word_count(closing),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# Cover letter — {ctx.job.title}", "", f"Dear {company},", ""]
        lines += [paragraph for paragraph in payload["paragraphs"]]
        lines += ["", payload["closing"], "", "Lyle Okoth"]
        return "\n".join(lines).strip() + "\n"
