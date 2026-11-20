"""Skill 6 — the short email the application is actually sent with."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, review_block, system_prompt
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
                    "Write the email a real person sends with this application, not a shortened cover\n"
                    "letter. 100-145 words in the body.\n"
                    "Subject: one specific hook from the company or the posting plus the role, under 90\n"
                    "characters. Never 'Application for' or 'Applying for'.\n"
                    "Open with the concrete thing that caught Lyle's attention from <research> or the\n"
                    "posting and why it connects to his work. Do not open with 'I am applying', 'I am\n"
                    "writing to apply' or a summary of his career. Tell one short story or moment from\n"
                    "the portfolio with one exact number, then say what he would want to work on with\n"
                    "this team. Close with one plain ask and mention the CV and cover letter in the same\n"
                    "sentence. Use contractions and ordinary spoken rhythm. No 'I hope this email finds\n"
                    "you well', no 'I am excited to apply', no stacked adjectives, no signature block\n"
                    "longer than 'Lyle'.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=6000)
                + "\n\n"
                + research_block(ctx, limit=2000)
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
        body = ground_text(strip_cliches(text(payload.get("body"), 1600)), ctx)
        body = clip_words(body, 150)
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
