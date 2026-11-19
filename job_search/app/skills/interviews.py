"""Skills 10–11 — technical and behavioural interview briefs."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_words, items, strip_cliches, text


class TechnicalInterviewSkill(Skill):
    name = "technical_interview"
    tier = "large"
    output_kind = "technical_interview"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 5_000

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["questions"],
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["topic", "difficulty", "question", "answer"],
                        "properties": {
                            "topic": {"type": "string", "max_len": 80},
                            "difficulty": {"type": "string", "enum": ["warm-up", "core", "deep"]},
                            "question": {"type": "string", "max_len": 400},
                            "answer": {"type": "string", "max_len": 2500},
                            "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
                            "grounded_in": {"type": "string", "max_len": 160},
                        },
                    },
                }
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        must = ", ".join((ctx.prior.get("job_extraction") or {}).get("must_have") or [])
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "technical_interview",
                    "Prepare 10–14 likely technical questions for this posting. Cover its must-haves: "
                    f"{must or 'the posted stack'}. Each answer is at most 220 words and says how Lyle "
                    "would answer in an interview, using portfolio projects as evidence. Add one or two "
                    "follow-ups per question. No trivia that is not in the posting or the portfolio.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=8000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx, limit=7000) + "\n\nWrite the technical interview JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        questions = []
        for row in payload.get("questions") or []:
            if not isinstance(row, dict):
                continue
            question = text(row.get("question"), 400)
            answer = ground_text(strip_cliches(text(row.get("answer"), 2500)), ctx)
            if not question or not answer:
                continue
            questions.append(
                {
                    "topic": text(row.get("topic"), 80) or "General",
                    "difficulty": row.get("difficulty") if row.get("difficulty") in {"warm-up", "core", "deep"} else "core",
                    "question": question,
                    "answer": clip_words(answer, 250),
                    "follow_ups": items(row.get("follow_ups"), 3, item_limit=300),
                    "grounded_in": text(row.get("grounded_in"), 160),
                }
            )
        return {"questions": questions[:14]}

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# Technical interview — {ctx.job.title} at {company}", ""]
        for index, row in enumerate(payload["questions"], start=1):
            lines += [
                f"## {index}. {row['question']}",
                f"**Topic:** {row['topic']} · **Level:** {row['difficulty']}",
                "",
                row["answer"],
            ]
            if row["follow_ups"]:
                lines += ["", "**Follow-ups:**", *[f"- {item}" for item in row["follow_ups"]]]
            if row["grounded_in"]:
                lines += ["", f"_Evidence: {row['grounded_in']}_"]
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class BehavioralInterviewSkill(Skill):
    name = "behavioral_interview"
    tier = "large"
    output_kind = "behavioral_interview"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 5_000

    def schema(self) -> dict[str, Any]:
        star = {
            "type": "object",
            "required": ["situation", "task", "action", "result"],
            "properties": {
                "situation": {"type": "string", "max_len": 400},
                "task": {"type": "string", "max_len": 400},
                "action": {"type": "string", "max_len": 900},
                "result": {"type": "string", "max_len": 400},
            },
        }
        return {
            "type": "object",
            "required": ["questions"],
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["competency", "question", "star", "answer"],
                        "properties": {
                            "competency": {"type": "string", "max_len": 80},
                            "question": {"type": "string", "max_len": 400},
                            "star": star,
                            "answer": {"type": "string", "max_len": 2500},
                        },
                    },
                }
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                system_prompt(
                    "behavioral_interview",
                    "Prepare 8–10 behavioural questions likely for this role. Use STAR, anchor every "
                    "story in a real portfolio project or role, and keep the spoken answer under 220 words. "
                    "No invented conflict or metrics.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=8000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx, limit=7000) + "\n\nWrite the behavioural interview JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        questions = []
        for row in payload.get("questions") or []:
            if not isinstance(row, dict):
                continue
            star = row.get("star") if isinstance(row.get("star"), dict) else {}
            answer = ground_text(strip_cliches(text(row.get("answer"), 2500)), ctx)
            question = text(row.get("question"), 400)
            if not question or not answer:
                continue
            questions.append(
                {
                    "competency": text(row.get("competency"), 80) or "Collaboration",
                    "question": question,
                    "star": {
                        key: ground_text(text(star.get(key), 900), ctx)
                        for key in ("situation", "task", "action", "result")
                    },
                    "answer": clip_words(answer, 250),
                }
            )
        return {"questions": questions[:10]}

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# Behavioural interview — {ctx.job.title} at {company}", ""]
        for index, row in enumerate(payload["questions"], start=1):
            lines += [f"## {index}. {row['question']}", f"**Competency:** {row['competency']}", ""]
            for label in ("situation", "task", "action", "result"):
                if row["star"][label]:
                    lines.append(f"**{label.title()}:** {row['star'][label]}")
            lines += ["", row["answer"], ""]
        return "\n".join(lines).strip() + "\n"
