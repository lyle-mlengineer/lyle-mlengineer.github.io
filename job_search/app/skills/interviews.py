"""Skills 10–11 — technical and behavioural interview briefs."""

from __future__ import annotations

from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import Skill, SkillContext, job_block
from .text import clip_words, items, strip_cliches, text


def _strings(value: Any, limit: int, *, item_limit: int = 300) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text_value = " ".join(str(item).split())[:item_limit]
        if text_value and text_value not in out:
            out.append(text_value)
    return out[:limit]


def _requirements(value: Any) -> dict[str, list[str]]:
    row = value if isinstance(value, dict) else {}
    return {
        "functional": _strings(row.get("functional"), 8),
        "non_functional": _strings(row.get("non_functional"), 8),
    }


def _entities(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if isinstance(item, str):
            name, fields, notes = item, [], ""
        elif isinstance(item, dict):
            name = " ".join(str(item.get("name") or "").split())[:120]
            fields = _strings(item.get("fields"), 12, item_limit=120)
            notes = " ".join(str(item.get("notes") or "").split())[:300]
        else:
            continue
        if name:
            rows.append({"name": name, "fields": fields, "notes": notes})
    return rows[:8]


def _class_design(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if isinstance(item, str):
            name, responsibility = item[:120], ""
            interfaces: list[str] = []
            collaborators: list[str] = []
        elif isinstance(item, dict):
            name = " ".join(str(item.get("name") or "").split())[:120]
            responsibility = " ".join(str(item.get("responsibility") or "").split())[:400]
            interfaces = _strings(item.get("interfaces"), 8, item_limit=200)
            collaborators = _strings(item.get("collaborators"), 8, item_limit=120)
        else:
            continue
        if name:
            rows.append(
                {
                    "name": name,
                    "responsibility": responsibility,
                    "interfaces": interfaces,
                    "collaborators": collaborators,
                }
            )
    return rows[:8]


def _api_design(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if isinstance(item, str):
            method, path, purpose = "", item[:200], ""
        elif isinstance(item, dict):
            method = " ".join(str(item.get("method") or "").split()).upper()[:12]
            path = " ".join(str(item.get("path") or "").split())[:180]
            purpose = " ".join(str(item.get("purpose") or "").split())[:300]
        else:
            continue
        if path or purpose:
            rows.append({"method": method, "path": path, "purpose": purpose})
    return rows[:10]


def _deep_dives(value: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if isinstance(item, str):
            title, detail = "Deep dive", item[:600]
        elif isinstance(item, dict):
            title = " ".join(str(item.get("title") or "").split())[:120] or "Deep dive"
            detail = " ".join(str(item.get("detail") or "").split())[:900]
        else:
            continue
        if detail:
            rows.append({"title": title, "detail": detail})
    return rows[:6]


def _design_lines(
    row: dict[str, Any], *, api_label: str = "API design", high_level_label: str = "High-level design"
) -> list[str]:
    """Render the common design-interview spine shared by HLD and LLD."""
    lines: list[str] = []
    requirements = row.get("requirements") or {}
    functional = requirements.get("functional") or []
    non_functional = requirements.get("non_functional") or []
    if functional or non_functional:
        lines += ["", "### Requirements"]
        if functional:
            lines += ["**Functional**", *[f"- {item}" for item in functional]]
        if non_functional:
            lines += ["", "**Non-functional**", *[f"- {item}" for item in non_functional]]
    entities = row.get("core_entities") or []
    if entities:
        lines += ["", "### Core entities"]
        for entity in entities:
            detail = ", ".join(entity.get("fields") or [])
            note = entity.get("notes") or ""
            entry = f"- **{entity['name']}**"
            if detail:
                entry += f" — {detail}"
            if note:
                entry += f". {note}"
            lines.append(entry)
    api = row.get("api_design") or []
    if api:
        lines += ["", f"### {api_label}"]
        for endpoint in api:
            if endpoint.get("method") and endpoint.get("path"):
                label = f"`{endpoint['method']} {endpoint['path']}`"
            else:
                label = f"`{endpoint.get('path') or endpoint.get('purpose')}`"
            purpose = endpoint.get("purpose") or ""
            lines.append(f"- {label}" + (f" — {purpose}" if purpose else ""))
    flow = row.get("data_flow") or []
    if flow:
        lines += ["", "### Data flow", *[f"{index}. {item}" for index, item in enumerate(flow, start=1)]]
    high_level = row.get("high_level") or []
    if high_level:
        lines += ["", f"### {high_level_label}", *[f"- {item}" for item in high_level]]
    if row.get("diagram"):
        lines += ["", "### Diagram", "", "```text", row["diagram"], "```"]
    deep_dives = row.get("deep_dives") or []
    if deep_dives:
        lines += ["", "### Deep dives"]
        for item in deep_dives:
            lines += [f"**{item['title']}** — {item['detail']}", ""]
        if lines[-1] == "":
            lines.pop()
    return lines


def _lld_lines(row: dict[str, Any]) -> list[str]:
    """Requirements -> entities -> class design -> implementation -> extensibility."""
    lines: list[str] = []
    requirements = row.get("requirements") or {}
    functional = requirements.get("functional") or []
    non_functional = requirements.get("non_functional") or []
    if functional or non_functional:
        lines += ["", "### Requirements"]
        if functional:
            lines += ["**Functional**", *[f"- {item}" for item in functional]]
        if non_functional:
            lines += ["", "**Non-functional**", *[f"- {item}" for item in non_functional]]
    entities = row.get("core_entities") or []
    data_structures = row.get("data_structures") or []
    if entities or data_structures:
        lines += ["", "### Entities"]
        for entity in entities:
            detail = ", ".join(entity.get("fields") or [])
            note = entity.get("notes") or ""
            entry = f"- **{entity['name']}**"
            if detail:
                entry += f" — {detail}"
            if note:
                entry += f". {note}"
            lines.append(entry)
        if data_structures:
            lines += ["", "**Key data structures**", *[f"- {item}" for item in data_structures]]
    classes = row.get("class_design") or []
    if classes:
        lines += ["", "### Class design"]
        for item in classes:
            entry = f"- **{item['name']}**"
            if item.get("responsibility"):
                entry += f" — {item['responsibility']}"
            parts = []
            if item.get("interfaces"):
                parts.append("Interfaces: " + "; ".join(item["interfaces"]))
            if item.get("collaborators"):
                parts.append("Collaborators: " + ", ".join(item["collaborators"]))
            if parts:
                entry += ". " + ". ".join(parts)
            lines.append(entry)
    if row.get("diagram"):
        lines += ["", "**Class diagram**", "", "```text", row["diagram"], "```"]
    implementation = row.get("implementation") or []
    if implementation:
        lines += ["", "### Implementation"]
        for item in implementation:
            lines += [f"**{item['title']}** — {item['detail']}", ""]
        if lines[-1] == "":
            lines.pop()
    extensibility = row.get("extensibility") or []
    if extensibility:
        lines += ["", "### Extensibility", *[f"- {item}" for item in extensibility]]
    return lines


def _interviewer_lines(row: dict[str, Any]) -> list[str]:
    questions = row.get("interviewer_questions") or []
    if not questions:
        return []
    return ["", "### Questions the interviewer may ask", *[f"- {item}" for item in questions]]


def _ask_lines(row: dict[str, Any]) -> list[str]:
    questions = row.get("questions_to_ask") or []
    if not questions:
        return []
    return ["", "### Questions to ask the interviewer", *[f"- {item}" for item in questions]]


def _code(value: Any) -> str:
    return str(value or "").replace(chr(13) + chr(10), chr(10)).replace(chr(96) * 3, "").strip()[:6000]


def _diagram(value: Any) -> str:
    """Keep an ASCII diagram ASCII: boxes and arrows survive the Markdown renderer."""
    raw = str(value or "")
    text = raw.replace(chr(13) + chr(10), chr(10)).replace(chr(96) * 3, "").strip()
    return text[:4_000]


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


class SystemDesignInterviewSkill(Skill):
    name = "system_design"
    tier = "large"
    output_kind = "system_design"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 12_000

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
                            "requirements": {
                                "type": "object",
                                "required": ["functional", "non_functional"],
                                "properties": {
                                    "functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                    "non_functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "core_entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string", "max_len": 120},
                                        "fields": {
                                            "type": "array",
                                            "items": {"type": "string", "max_len": 120},
                                        },
                                        "notes": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "api_design": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["method", "path", "purpose"],
                                    "properties": {
                                        "method": {"type": "string", "max_len": 12},
                                        "path": {"type": "string", "max_len": 180},
                                        "purpose": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "data_flow": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "high_level": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "deep_dives": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["title", "detail"],
                                    "properties": {
                                        "title": {"type": "string", "max_len": 120},
                                        "detail": {"type": "string", "max_len": 900},
                                    },
                                },
                            },
                            "diagram": {"type": "string", "max_len": 4000},
                            "trade_offs": {"type": "array", "items": {"type": "string", "max_len": 220}},
                            "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
                            "interviewer_questions": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
                            "questions_to_ask": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
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
                    "system_design",
                    "Prepare 6–8 system design interview questions likely for this posting. Cover the "
                    f"posted stack ({must or 'the role requirements'}) and the scale implied by the product. "
                    "Work each design through the full interview flow, in this order: requirements "
                    "(functional and non-functional), core entities, API design, data flow, high-level "
                    "design, then two or three deep dives. Name the bottleneck and the trade-offs. For ML "
                    "and data systems, say what is trained or ingested, how the offline pipeline differs "
                    "from the online path, and where quality is measured. Include a compact ASCII diagram "
                    "using only boxes, arrows and labels. The answer field is a 120–180 word spoken "
                    "walkthrough, not a repeat of the sections. Include questions the interviewer is "
                    "likely to ask, three or four targeted questions the candidate should ask the "
                    "interviewer about this design and this company, and two or three follow-ups. Use "
                    "portfolio projects as evidence where they fit. Do not invent traffic, latency or cost "
                    "numbers.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=8000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx, limit=7000) + "\n\nWrite the system design interview JSON.",
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
                    "topic": text(row.get("topic"), 80) or "System design",
                    "difficulty": row.get("difficulty")
                    if row.get("difficulty") in {"warm-up", "core", "deep"}
                    else "core",
                    "question": question,
                    "answer": clip_words(answer, 200),
                    "requirements": _requirements(row.get("requirements")),
                    "core_entities": _entities(row.get("core_entities")),
                    "api_design": _api_design(row.get("api_design")),
                    "data_flow": _strings(row.get("data_flow"), 8, item_limit=400),
                    "high_level": _strings(row.get("high_level"), 8, item_limit=400),
                    "deep_dives": _deep_dives(row.get("deep_dives")),
                    "diagram": _diagram(row.get("diagram")),
                    "trade_offs": items(row.get("trade_offs"), 4, item_limit=220),
                    "follow_ups": items(row.get("follow_ups"), 3, item_limit=300),
                    "interviewer_questions": _strings(
                        row.get("interviewer_questions"), 5, item_limit=300
                    ),
                    "questions_to_ask": _strings(row.get("questions_to_ask"), 4, item_limit=300),
                    "grounded_in": text(row.get("grounded_in"), 160),
                }
            )
        return {"questions": questions[:8]}

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# System design interview — {ctx.job.title} at {company}", ""]
        for index, row in enumerate(payload["questions"], start=1):
            lines += [
                f"## {index}. {row['question']}",
                f"**Topic:** {row['topic']} · **Level:** {row['difficulty']}",
                "",
                row["answer"],
            ]
            lines += _design_lines(row)
            if row["trade_offs"]:
                lines += ["", "### Trade-offs", *[f"- {item}" for item in row["trade_offs"]]]
            lines += _interviewer_lines(row)
            lines += _ask_lines(row)
            if row["follow_ups"]:
                lines += ["", "### Follow-ups", *[f"- {item}" for item in row["follow_ups"]]]
            if row["grounded_in"]:
                lines += ["", f"_Evidence: {row['grounded_in']}_"]
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class LowLevelDesignInterviewSkill(Skill):
    name = "low_level_design"
    tier = "large"
    output_kind = "low_level_design"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 12_000

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
                            "question": {"type": "string", "max_len": 500},
                            "answer": {"type": "string", "max_len": 2600},
                            "requirements": {
                                "type": "object",
                                "properties": {
                                    "functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                    "non_functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "core_entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string", "max_len": 120},
                                        "fields": {
                                            "type": "array",
                                            "items": {"type": "string", "max_len": 120},
                                        },
                                        "notes": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "api_design": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["path", "purpose"],
                                    "properties": {
                                        "method": {"type": "string", "max_len": 12},
                                        "path": {"type": "string", "max_len": 180},
                                        "purpose": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "data_flow": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "high_level": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "deep_dives": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["title", "detail"],
                                    "properties": {
                                        "title": {"type": "string", "max_len": 120},
                                        "detail": {"type": "string", "max_len": 900},
                                    },
                                },
                            },
                            "diagram": {"type": "string", "max_len": 4000},
                            "class_design": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "responsibility"],
                                    "properties": {
                                        "name": {"type": "string", "max_len": 120},
                                        "responsibility": {"type": "string", "max_len": 400},
                                        "interfaces": {
                                            "type": "array",
                                            "items": {"type": "string", "max_len": 200},
                                        },
                                        "collaborators": {
                                            "type": "array",
                                            "items": {"type": "string", "max_len": 120},
                                        },
                                    },
                                },
                            },
                            "implementation": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["title", "detail"],
                                    "properties": {
                                        "title": {"type": "string", "max_len": 120},
                                        "detail": {"type": "string", "max_len": 900},
                                    },
                                },
                            },
                            "extensibility": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 400},
                            },
                            "components": {"type": "array", "items": {"type": "string", "max_len": 220}},
                            "data_structures": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 220},
                            },
                            "trade_offs": {"type": "array", "items": {"type": "string", "max_len": 220}},
                            "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
                            "interviewer_questions": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
                            "questions_to_ask": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
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
                    "low_level_design",
                    "Prepare 5–7 low-level design interview questions likely for this posting. This is the "
                    "class-and-function level, not the whiteboard architecture level: interfaces, data "
                    "structures, state machines, concurrency, error handling, tests and extension points. "
                    f"Cover the posted stack ({must or 'the role requirements'}) and the kind of code the team "
                    "actually ships. Follow this exact structure: requirements (functional and "
                    "non-functional), entities, class design (each class, its responsibility, interfaces and "
                    "collaborators), implementation (state, concurrency, error handling and tests), then "
                    "extensibility (extension points and what would break). Include a compact ASCII class or "
                    "sequence diagram using only boxes, arrows and labels. The answer field is a 120–180 word "
                    "spoken walkthrough, not a repeat of the sections. Name the key data structures and the "
                    "trade-offs explicitly. Include questions the interviewer is likely to "
                    "ask, three or four targeted questions the candidate should ask the interviewer about the "
                    "codebase and this team, and two or three follow-ups. Use portfolio projects as evidence "
                    "where they fit and do not invent numbers.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=8000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx, limit=7000) + "\n\nWrite the low-level design interview JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        questions = []
        for row in payload.get("questions") or []:
            if not isinstance(row, dict):
                continue
            question = text(row.get("question"), 500)
            answer = ground_text(strip_cliches(text(row.get("answer"), 2600)), ctx)
            if not question or not answer:
                continue
            questions.append(
                {
                    "topic": text(row.get("topic"), 80) or "Low-level design",
                    "difficulty": row.get("difficulty")
                    if row.get("difficulty") in {"warm-up", "core", "deep"}
                    else "core",
                    "question": question,
                    "answer": clip_words(answer, 200),
                    "requirements": _requirements(row.get("requirements")),
                    "core_entities": _entities(row.get("core_entities")),
                    "api_design": _api_design(row.get("api_design")),
                    "data_flow": _strings(row.get("data_flow"), 8, item_limit=400),
                    "high_level": _strings(row.get("high_level"), 8, item_limit=400),
                    "deep_dives": _deep_dives(row.get("deep_dives")),
                    "diagram": _diagram(row.get("diagram")),
                    "class_design": _class_design(row.get("class_design")),
                    "implementation": _deep_dives(row.get("implementation")),
                    "extensibility": _strings(row.get("extensibility"), 6, item_limit=400),
                    "components": items(row.get("components"), 5, item_limit=220),
                    "data_structures": items(row.get("data_structures"), 5, item_limit=220),
                    "trade_offs": items(row.get("trade_offs"), 4, item_limit=220),
                    "follow_ups": items(row.get("follow_ups"), 3, item_limit=300),
                    "interviewer_questions": _strings(
                        row.get("interviewer_questions"), 5, item_limit=300
                    ),
                    "questions_to_ask": _strings(row.get("questions_to_ask"), 4, item_limit=300),
                    "grounded_in": text(row.get("grounded_in"), 160),
                }
            )
        return {"questions": questions[:7]}

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# Low-level design interview — {ctx.job.title} at {company}", ""]
        for index, row in enumerate(payload["questions"], start=1):
            lines += [
                f"## {index}. {row['question']}",
                f"**Topic:** {row['topic']} · **Level:** {row['difficulty']}",
                "",
                row["answer"],
            ]
            lines += _lld_lines(row)
            if row["trade_offs"]:
                lines += ["", "### Trade-offs", *[f"- {item}" for item in row["trade_offs"]]]
            lines += _interviewer_lines(row)
            lines += _ask_lines(row)
            if row["follow_ups"]:
                lines += ["", "### Follow-ups", *[f"- {item}" for item in row["follow_ups"]]]
            if row["grounded_in"]:
                lines += ["", f"_Evidence: {row['grounded_in']}_"]
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class CodingInterviewSkill(Skill):
    name = "coding"
    tier = "large"
    output_kind = "coding"
    requires = ("job_extraction",)
    weight = 3.0
    optional = True
    max_tokens = 12_000

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["problems"],
            "properties": {
                "problems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["topic", "difficulty", "question", "answer", "code"],
                        "properties": {
                            "topic": {"type": "string", "max_len": 80},
                            "difficulty": {"type": "string", "enum": ["warm-up", "core", "deep"]},
                            "question": {"type": "string", "max_len": 500},
                            "answer": {"type": "string", "max_len": 2000},
                            "approach": {"type": "string", "max_len": 900},
                            "requirements": {
                                "type": "object",
                                "properties": {
                                    "functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                    "non_functional": {
                                        "type": "array",
                                        "items": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "core_entities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string", "max_len": 120},
                                        "fields": {
                                            "type": "array",
                                            "items": {"type": "string", "max_len": 120},
                                        },
                                        "notes": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "api_design": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["path", "purpose"],
                                    "properties": {
                                        "method": {"type": "string", "max_len": 12},
                                        "path": {"type": "string", "max_len": 180},
                                        "purpose": {"type": "string", "max_len": 300},
                                    },
                                },
                            },
                            "data_flow": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "high_level": {"type": "array", "items": {"type": "string", "max_len": 400}},
                            "deep_dives": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["title", "detail"],
                                    "properties": {
                                        "title": {"type": "string", "max_len": 120},
                                        "detail": {"type": "string", "max_len": 900},
                                    },
                                },
                            },
                            "diagram": {"type": "string", "max_len": 4000},
                            "interviewer_questions": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
                            "questions_to_ask": {
                                "type": "array",
                                "items": {"type": "string", "max_len": 300},
                            },
                            "slow_approach": {"type": "string", "max_len": 900},
                            "slow_code": {"type": "string", "max_len": 6000},
                            "slow_time_complexity": {"type": "string", "max_len": 120},
                            "slow_space_complexity": {"type": "string", "max_len": 120},
                            "time_complexity": {"type": "string", "max_len": 120},
                            "space_complexity": {"type": "string", "max_len": 120},
                            "code": {"type": "string", "max_len": 6000},
                            "language": {"type": "string", "max_len": 30},
                            "complexity": {"type": "string", "max_len": 120},
                            "edge_cases": {"type": "array", "items": {"type": "string", "max_len": 200}},
                            "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
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
                    "coding",
                    "Prepare 6–8 coding interview problems likely for this posting. Cover its must-haves "
                    f"({must or 'the posted stack'}) and the kind of code the team actually ships. Work each "
                    "problem through the design flow: requirements (functional and non-functional, meaning "
                    "input/output contract and complexity budget), core entities (the data structures), API "
                    "design (the exact function signature), data flow (the algorithm step by step), a "
                    "high-level solution outline, then two or three deep dives on the tricky parts. Include a "
                    "compact ASCII diagram of the algorithm or data structure using only boxes, arrows and "
                    "labels. The answer field is a spoken walkthrough of at most 180 words (brute force, then "
                    "the better approach, then complexity), not a repeat of the sections. Then give a short "
                    "reference solution in Python using only the standard library unless the posting names "
                    "another language. Include the obvious slow solution first (with its own code, runtime "
                    "and storage), then the optimised solution with its runtime and storage stated "
                    "separately. Add edge cases, questions the interviewer may ask, three or four targeted "
                    "questions the candidate should ask about the team or codebase, and two follow-ups. Keep "
                    "each solution under 80 lines. Do not invent experience.",
                ),
            ),
            ChatMessage(
                "user",
                job_block(ctx, limit=8000) + "\n\n" + research_block(ctx, limit=2500) + "\n\n"
                + portfolio_block(ctx, limit=7000) + "\n\nWrite the coding interview JSON.",
            ),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        problems = []
        for row in payload.get("problems") or []:
            if not isinstance(row, dict):
                continue
            question = text(row.get("question"), 500)
            answer = ground_text(strip_cliches(text(row.get("answer"), 2000)), ctx)
            if not question or not answer:
                continue
            time_complexity = text(row.get("time_complexity"), 120)
            space_complexity = text(row.get("space_complexity"), 120)
            complexity = text(row.get("complexity"), 120)
            if not complexity and (time_complexity or space_complexity):
                complexity = (
                    f"{time_complexity or 'not stated'} time · "
                    f"{space_complexity or 'not stated'} space"
                )
            problems.append(
                {
                    "topic": text(row.get("topic"), 80) or "Coding",
                    "difficulty": row.get("difficulty")
                    if row.get("difficulty") in {"warm-up", "core", "deep"}
                    else "core",
                    "question": question,
                    "answer": clip_words(answer, 200),
                    "requirements": _requirements(row.get("requirements")),
                    "core_entities": _entities(row.get("core_entities")),
                    "api_design": _api_design(row.get("api_design")),
                    "data_flow": _strings(row.get("data_flow"), 8, item_limit=400),
                    "high_level": _strings(row.get("high_level"), 8, item_limit=400),
                    "deep_dives": _deep_dives(row.get("deep_dives")),
                    "diagram": _diagram(row.get("diagram")),
                    "slow_approach": text(row.get("slow_approach"), 900),
                    "slow_code": _code(row.get("slow_code")),
                    "slow_time_complexity": text(row.get("slow_time_complexity"), 120),
                    "slow_space_complexity": text(row.get("slow_space_complexity"), 120),
                    "approach": text(row.get("approach"), 900),
                    "code": _code(row.get("code")),
                    "language": text(row.get("language"), 30) or "Python",
                    "time_complexity": time_complexity,
                    "space_complexity": space_complexity,
                    "complexity": complexity,
                    "edge_cases": items(row.get("edge_cases"), 5, item_limit=200),
                    "follow_ups": items(row.get("follow_ups"), 3, item_limit=300),
                    "interviewer_questions": _strings(
                        row.get("interviewer_questions"), 5, item_limit=300
                    ),
                    "questions_to_ask": _strings(row.get("questions_to_ask"), 4, item_limit=300),
                }
            )
        return {"problems": problems[:8]}

    def render(self, payload: dict[str, Any], ctx: SkillContext) -> str:
        company = ctx.company.name if ctx.company else "the company"
        lines = [f"# Coding interview — {ctx.job.title} at {company}", ""]
        for index, row in enumerate(payload["problems"], start=1):
            level = f"**Topic:** {row['topic']} · **Level:** {row['difficulty']}"
            if row["complexity"]:
                level += f" · **{row['complexity']}**"
            lines += [f"## {index}. {row['question']}", level, "", row["answer"]]
            lines += _design_lines(
                row, api_label="API / function signature", high_level_label="Solution outline"
            )
            language = row["language"].lower().replace(" ", "-")
            has_slow = bool(
                row.get("slow_approach")
                or row.get("slow_code")
                or row.get("slow_time_complexity")
                or row.get("slow_space_complexity")
            )
            if has_slow:
                lines += ["", "### Obvious solution"]
                if row.get("slow_approach"):
                    lines += ["", row["slow_approach"]]
                if row.get("slow_code"):
                    lines += ["", f"```{language}", row["slow_code"], "```"]
                lines += [
                    "",
                    f"**Runtime:** {row.get('slow_time_complexity') or 'not stated'}",
                    f"**Storage:** {row.get('slow_space_complexity') or 'not stated'}",
                ]
            lines += ["", "### Optimised solution"]
            if row.get("approach"):
                lines += ["", row["approach"]]
            if row.get("code"):
                lines += ["", f"```{language}", row["code"], "```"]
            lines += [
                "",
                f"**Runtime:** {row.get('time_complexity') or row.get('complexity') or 'not stated'}",
                f"**Storage:** {row.get('space_complexity') or 'not stated'}",
            ]
            if row["edge_cases"]:
                lines += ["", "### Edge cases", *[f"- {item}" for item in row["edge_cases"]]]
            lines += _interviewer_lines(row)
            lines += _ask_lines(row)
            if row["follow_ups"]:
                lines += ["", "### Follow-ups", *[f"- {item}" for item in row["follow_ups"]]]
            lines.append("")
        return "\n".join(lines).strip() + "\n"
