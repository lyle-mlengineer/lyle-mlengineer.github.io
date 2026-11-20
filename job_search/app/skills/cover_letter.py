"""Skill 5 — a 350-word cover letter that names the real company and role."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_chars, clip_words, drop_placeholders, items, strip_cliches, text, word_count


class CoverLetterSkill(Skill):
    name = "cover_letter"
    tier = "large"
    output_kind = "cover_letter"
    requires = ("job_extraction", "company_research")
    weight = 2.0
    max_tokens = 3_000

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["greeting", "paragraphs", "closing"],
            "properties": {
                # Generation caps are deliberately loose: the postprocessor is
                # the single place that clips, so an over-long closing is a
                # normalisation job rather than a failed run.
                "greeting": {"type": "string", "min_len": 3, "max_len": 400},
                "paragraphs": {"type": "array", "items": {"type": "string", "min_len": 60, "max_len": 900}},
                "closing": {"type": "string", "min_len": 3, "max_len": 400},
                "word_count": {"type": "integer"},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "cover_letter",
                    "Write a one-page cover letter for this role. Three or four paragraphs, 280-340 words.\n"
                    "Structure it as an argument, not a summary of the CV:\n"
                    "1. Name the role and company, then open with one specific, verifiable observation from\n"
                    "   <research> (a product, a launch, a technical constraint, a market). Do not open with\n"
                    "   'I am writing to apply' or a compliment that could apply to any company.\n"
                    "2. Take the two most important requirements from <job> and answer each with one concrete\n"
                    "   piece of <portfolio> evidence, including the exact number and the trade-off made.\n"
                    "3. Say what Lyle would do in the first 90 days in this role, tied to the team's actual work.\n"
                    "   No generic promises about learning or contributing.\n"
                    "4. Close with a concrete next step (a call, a walkthrough, availability). Do not beg.\n"
                    "Use the company's name in the greeting. No letterhead, no address block, no bullet lists.\n"
                    "Every paragraph must contain a fact that only Lyle could write.",
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
        company = ctx.company.name if ctx.company else "your team"
        greeting = clip_chars(strip_cliches(text(payload.get("greeting"), 400)), 120)
        if len(greeting) < 4 or "hiring manager" in greeting.lower():
            greeting = f"Dear {company} team,"
        closing = clip_chars(strip_cliches(text(payload.get("closing"), 400)), 120)
        if len(closing) < 3:
            closing = "Sincerely,"
        paragraphs: list[str] = []
        for value in items(payload.get("paragraphs"), 5, item_limit=900):
            paragraph = ground_text(strip_cliches(value), ctx)
            if paragraph and paragraph not in paragraphs:
                paragraphs.append(paragraph)
        paragraphs = drop_placeholders(paragraphs)
        allowed = max(0, 350 - word_count(greeting) - word_count(closing))
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
        lines = [f"# Cover letter — {ctx.job.title}", "", payload["greeting"], ""]
        lines += [paragraph for paragraph in payload["paragraphs"]]
        lines += ["", payload["closing"], "", "Lyle Okoth"]
        return "\n".join(lines).strip() + "\n"
