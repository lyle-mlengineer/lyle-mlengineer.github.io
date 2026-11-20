"""Skill 6 — the short email the application is actually sent with."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, review_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_words, drop_placeholders, items, strip_cliches, text, word_count


class EmailWritingSkill(Skill):
    name = "email_writing"
    tier = "large"
    output_kind = "email"
    requires = ("cover_letter",)
    weight = 1.0
    optional = True
    max_tokens = 1_400

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["subject", "body"],
            "properties": {
                "subject": {"type": "string", "min_len": 4, "max_len": 120},
                "body": {"type": "string", "min_len": 40, "max_len": 1400},
                "attachment_names": {"type": "array", "items": {"type": "string", "max_len": 160}},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "email_writing",
                    "Write the email Lyle sends with this application. 110-150 words in the body.\n"
                    "Subject: the role plus one specific proof point, under 90 characters. Never\n"
                    "'Application for' or 'Applying for'.\n"
                    "Body: first sentence names the role and one concrete hook from the company or the\n"
                    "posting. Second and third sentences carry the strongest portfolio evidence with an\n"
                    "exact number from <portfolio>. Close with one clear ask and state that the CV and\n"
                    "cover letter are attached. No 'I hope this email finds you well', no 'I am excited\n"
                    "to apply', no signature block longer than 'Lyle Okoth'.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=6000)
                + "\n\n"
                + review_block(ctx, names=("cover_letter",), limit=3000)
                + "\n\n"
                + portfolio_block(ctx, limit=3500)
                + "\n\nWrite the email JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        role = ctx.job.title
        company = ctx.company.name if ctx.company else "the company"
        subject = strip_cliches(text(payload.get("subject"), 120)) or f"Application — {role}"
        subject = subject.strip(" .-")[:100]
        if role.lower() not in subject.lower():
            subject = f"{subject[:80]} — {role}"[:100]
        body = ground_text(strip_cliches(text(payload.get("body"), 1600)), ctx)
        body = clip_words(body, 165)
        attachments = drop_placeholders(items(payload.get("attachment_names"), 6, item_limit=160))
        if not attachments:
            attachments = ["CV", "Cover letter"]
        return {
            "subject": subject,
            "body": body,
            "attachment_names": attachments,
            "word_count": word_count(body),
            "company": company,
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        return (
            f"# Email — {ctx.job.title}\n\n"
            f"**To:** {ctx.company.name if ctx.company else 'the hiring team'}\n\n"
            f"**Subject:** {payload['subject']}\n\n"
            f"{payload['body']}\n\n"
            f"**Attach:** {', '.join(payload['attachment_names'])}\n"
        )
