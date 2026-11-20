"""Skills 7–9 — the answers Lyle says out loud."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_words, items, prose_text, strip_cliches, text, word_count


class _SpokenSkill(Skill):
    tier = "small"
    optional = True
    weight = 1.0
    max_tokens = 1_500

    def _common_system(self, cue: str) -> str:
        return system_prompt(
            self.name,
            f"{cue} Write 150–220 words in the first person, as something Lyle would actually say. "
            "Break it into 2–3 short paragraphs of at most three sentences, separated by a blank line, "
            "so it can be read out loud without losing the thread. "
            "Keep delivery notes separate and practical. Anchor claims in the portfolio.",
        )

    def _answer(self, value: Any, ctx: SkillContext) -> str:
        answer = ground_text(strip_cliches(prose_text(value, 5000)), ctx)
        answer = clip_words(answer, 220)
        if word_count(answer) < 150:
            return answer  # short is acceptable; padding would invent
        return answer


class TellMeAboutYourselfSkill(_SpokenSkill):
    name = "tell_me_about_yourself"
    output_kind = "tell_me_about_yourself"
    requires = ("job_extraction",)

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["answer", "delivery_notes", "anchor_points"],
            "properties": {
                "answer": {"type": "string", "min_len": 200, "max_len": 5000},
                "delivery_notes": {"type": "array", "items": {"type": "string", "max_len": 240}},
                "anchor_points": {"type": "array", "items": {"type": "string", "max_len": 240}},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                self._common_system(
                    "Tell the story of how Lyle got here and why this role is the next step. "
                    "It must be a narration, not a fact list or a resume summary: start in the "
                    "present, turn to the choice or moment that led him into speech and ML, "
                    "prove it with one or two concrete scenes, then land on why this team. "
                    "Use ordinary spoken sentences and connect the beats with cause and effect. "
                    "Do not enumerate roles, metrics or skills, and do not open with "
                    "'I am a ... engineer'. A number can appear inside a story, never as a "
                    "standalone credential."
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=7000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx) + "\n\nWrite the answer JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        return {
            "answer": self._answer(payload.get("answer"), ctx),
            "delivery_notes": items(payload.get("delivery_notes"), 5, item_limit=240),
            "anchor_points": items(payload.get("anchor_points"), 6, item_limit=240),
            "word_count": word_count(self._answer(payload.get("answer"), ctx)),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = _header(ctx, company, "Tell me about yourself")
        lines += [payload["answer"], ""]
        if payload["anchor_points"]:
            lines += ["## Anchors", *[f"- {item}" for item in payload["anchor_points"]], ""]
        if payload["delivery_notes"]:
            lines += ["## Delivery", *[f"- {item}" for item in payload["delivery_notes"]]]
        return "\n".join(lines).strip() + "\n"


class WorkHistorySkill(_SpokenSkill):
    name = "work_history"
    output_kind = "work_history"
    requires = ("job_extraction",)

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["answer", "timeline", "delivery_notes"],
            "properties": {
                "answer": {"type": "string", "min_len": 200, "max_len": 5000},
                "timeline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["company", "role", "years", "proof"],
                        "properties": {
                            "company": {"type": "string", "max_len": 120},
                            "role": {"type": "string", "max_len": 120},
                            "years": {"type": "string", "max_len": 40},
                            "proof": {"type": "string", "max_len": 260},
                        },
                    },
                },
                "delivery_notes": {"type": "array", "items": {"type": "string", "max_len": 240}},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage("system", self._common_system("Answer 'Walk me through your work history' for this role.")),
            ChatMessage(
                "user",
                job_block(ctx, limit=7000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx) + "\n\nWrite the answer JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        timeline = []
        for row in payload.get("timeline") or []:
            if isinstance(row, dict) and text(row.get("company"), 120) and text(row.get("role"), 120):
                timeline.append(
                    {
                        "company": text(row.get("company"), 120),
                        "role": text(row.get("role"), 120),
                        "years": text(row.get("years"), 40),
                        "proof": ground_text(text(row.get("proof"), 260), ctx),
                    }
                )
        return {
            "answer": self._answer(payload.get("answer"), ctx),
            "timeline": timeline[:6],
            "delivery_notes": items(payload.get("delivery_notes"), 5, item_limit=240),
            "word_count": word_count(self._answer(payload.get("answer"), ctx)),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = _header(ctx, company, "Work history")
        lines += [payload["answer"], ""]
        if payload["timeline"]:
            lines += ["## Timeline"]
            for row in payload["timeline"]:
                lines.append(f"- **{row['role']}, {row['company']}** ({row['years']}) — {row['proof']}")
            lines.append("")
        if payload["delivery_notes"]:
            lines += ["## Delivery", *[f"- {item}" for item in payload["delivery_notes"]]]
        return "\n".join(lines).strip() + "\n"


class ProudProjectSkill(_SpokenSkill):
    name = "proud_project"
    output_kind = "proud_project"
    requires = ("job_extraction",)

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["answer", "projects", "delivery_notes"],
            "properties": {
                "answer": {"type": "string", "min_len": 200, "max_len": 5000},
                "projects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "why", "what_i_built", "impact"],
                        "properties": {
                            "name": {"type": "string", "max_len": 120},
                            "why": {"type": "string", "max_len": 260},
                            "what_i_built": {"type": "string", "max_len": 500},
                            "impact": {"type": "string", "max_len": 260},
                            "stack": {"type": "array", "items": {"type": "string", "max_len": 60}},
                        },
                    },
                },
                "delivery_notes": {"type": "array", "items": {"type": "string", "max_len": 240}},
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage("system", self._common_system("Answer 'Tell me about a project you are proud of' for this role.")),
            ChatMessage(
                "user",
                job_block(ctx, limit=7000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx) + "\n\nWrite the answer JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        projects = []
        for row in payload.get("projects") or []:
            if not isinstance(row, dict) or not text(row.get("name"), 120):
                continue
            projects.append(
                {
                    "name": text(row.get("name"), 120),
                    "why": ground_text(text(row.get("why"), 260), ctx),
                    "what_i_built": ground_text(text(row.get("what_i_built"), 500), ctx),
                    "impact": ground_text(text(row.get("impact"), 260), ctx),
                    "stack": items(row.get("stack"), 8, item_limit=60),
                }
            )
        answer = self._answer(payload.get("answer"), ctx)
        return {
            "answer": answer,
            "projects": projects[:3],
            "delivery_notes": items(payload.get("delivery_notes"), 5, item_limit=240),
            "word_count": word_count(answer),
        }

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = _header(ctx, company, "A project I am proud of")
        lines += [payload["answer"], ""]
        for row in payload["projects"]:
            lines += [f"## {row['name']}", row["why"], "", row["what_i_built"], f"**Impact:** {row['impact']}"]
            if row["stack"]:
                lines += [f"**Stack:** {', '.join(row['stack'])}"]
            lines.append("")
        if payload["delivery_notes"]:
            lines += ["## Delivery", *[f"- {item}" for item in payload["delivery_notes"]]]
        return "\n".join(lines).strip() + "\n"


def _header(ctx: SkillContext, company: str, title: str) -> list[str]:
    return [f"# {title} — {ctx.job.title} at {company}", ""]
