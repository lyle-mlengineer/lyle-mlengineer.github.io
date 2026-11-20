"""Staged system design generation.

The outline call only picks questions. Each subcomponent is written by a small
follow-up call when the candidate opens the question, so a single call never has
to hold the whole design.
"""

from __future__ import annotations

import json
from typing import Any

from ..jobs.prompts import ground_text, portfolio_block, research_block, system_prompt
from ..providers.llm.base import ChatMessage
from .base import SkillContext, job_block
from .text import clip_words, items, strip_cliches, text

SYSTEM_DESIGN_SECTIONS = (
    "requirements",
    "entities",
    "api",
    "data_flow",
    "high_level",
    "deep_dives",
    "questions",
)

SECTION_LABELS = {
    "requirements": "requirements",
    "entities": "core entities",
    "api": "API design",
    "data_flow": "data flow",
    "high_level": "high-level design",
    "deep_dives": "deep dives",
    "questions": "interviewer questions",
    "follow_ups": "follow-ups",
}

SECTION_INSTRUCTIONS = {
    "requirements": (
        "List 4-6 functional requirements and 3-5 non-functional requirements. Each non-functional "
        "requirement should name the quality and the bound the design must hold, but do not invent "
        "traffic, latency or cost numbers."
    ),
    "entities": (
        "Name 4-7 core entities. For each, give the fields that matter to the design and one note "
        "about identity, lifecycle or access. Keep fields short."
    ),
    "api": (
        "Give 4-7 endpoints or operations. Include method, path and the single job the endpoint does. "
        "Prefer the smallest API that supports the functional requirements."
    ),
    "data_flow": (
        "Write 5-7 numbered steps from request or ingestion to durable state and back. Say where "
        "validation, caching, model inference or asynchronous work sits."
    ),
    "high_level": (
        "Give 4-6 high-level components and what each owns. Then draw a compact ASCII diagram with "
        "boxes, arrows and labels only. Finally write a 120-180 word spoken walkthrough in answer: "
        "how you would present this design at a whiteboard, not a repeat of the bullets."
    ),
    "deep_dives": (
        "Write 2-3 deep dives. Each one names a bottleneck, the failure mode, and the decision you "
        "would defend. Then give 3-4 trade-offs, each a single sentence with both sides."
    ),
    "questions": (
        "Write 4-5 questions the interviewer is likely to ask about this design, and 3-4 targeted "
        "questions the candidate should ask about this design and this company. Questions only."
    ),
    "follow_ups": (
        "Write 2-3 follow-up questions the interviewer may ask next, specific to the submitted design."
    ),
}


def section_schema(section: str) -> dict[str, Any]:
    string_list = {"type": "array", "items": {"type": "string", "max_len": 400}}
    if section == "requirements":
        return {
            "type": "object",
            "required": ["requirements"],
            "properties": {
                "requirements": {
                    "type": "object",
                    "required": ["functional", "non_functional"],
                    "properties": {
                        "functional": {"type": "array", "items": {"type": "string", "max_len": 300}},
                        "non_functional": {"type": "array", "items": {"type": "string", "max_len": 300}},
                    },
                }
            },
        }
    if section == "entities":
        return {
            "type": "object",
            "required": ["core_entities"],
            "properties": {
                "core_entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string", "max_len": 120},
                            "fields": {"type": "array", "items": {"type": "string", "max_len": 120}},
                            "notes": {"type": "string", "max_len": 300},
                        },
                    },
                }
            },
        }
    if section == "api":
        return {
            "type": "object",
            "required": ["api_design"],
            "properties": {
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
                }
            },
        }
    if section == "data_flow":
        return {"type": "object", "required": ["data_flow"], "properties": {"data_flow": string_list}}
    if section == "high_level":
        return {
            "type": "object",
            "required": ["answer", "high_level", "diagram"],
            "properties": {
                "answer": {"type": "string", "max_len": 2500},
                "high_level": string_list,
                "diagram": {"type": "string", "max_len": 4000},
                "grounded_in": {"type": "string", "max_len": 160},
            },
        }
    if section == "deep_dives":
        return {
            "type": "object",
            "required": ["deep_dives", "trade_offs"],
            "properties": {
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
                "trade_offs": {"type": "array", "items": {"type": "string", "max_len": 220}},
            },
        }
    if section == "questions":
        return {
            "type": "object",
            "required": ["interviewer_questions", "questions_to_ask"],
            "properties": {
                "interviewer_questions": {"type": "array", "items": {"type": "string", "max_len": 300}},
                "questions_to_ask": {"type": "array", "items": {"type": "string", "max_len": 300}},
            },
        }
    if section == "follow_ups":
        return {
            "type": "object",
            "required": ["follow_ups"],
            "properties": {"follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}}},
        }
    raise ValueError(f"unknown system design section: {section}")


def _section_present(row: dict[str, Any], section: str) -> bool:
    if section == "requirements":
        requirements = row.get("requirements") or {}
        return bool(requirements.get("functional") or requirements.get("non_functional"))
    if section == "entities":
        return bool(row.get("core_entities"))
    if section == "api":
        return bool(row.get("api_design"))
    if section == "data_flow":
        return bool(row.get("data_flow"))
    if section == "high_level":
        return bool(row.get("answer") or row.get("high_level") or row.get("diagram"))
    if section == "deep_dives":
        return bool(row.get("deep_dives") or row.get("trade_offs"))
    if section == "questions":
        return bool(row.get("interviewer_questions") or row.get("questions_to_ask"))
    return False


def loaded_sections(row: dict[str, Any]) -> list[str]:
    present = [section for section in SYSTEM_DESIGN_SECTIONS if _section_present(row, section)]
    stored = row.get("loaded_sections")
    if isinstance(stored, list):
        for section in stored:
            if section in SYSTEM_DESIGN_SECTIONS and section not in present:
                present.append(section)
    return [section for section in SYSTEM_DESIGN_SECTIONS if section in present]


def normalize_question(row: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
    from .interviews import _api_design, _deep_dives, _diagram, _entities, _requirements, _strings

    question = {
        "topic": text(row.get("topic"), 80) or "System design",
        "difficulty": row.get("difficulty")
        if row.get("difficulty") in {"warm-up", "core", "deep"}
        else "core",
        "question": text(row.get("question"), 400),
        "answer": clip_words(ground_text(strip_cliches(text(row.get("answer"), 2500)), ctx), 200),
        "requirements": _requirements(row.get("requirements")),
        "core_entities": _entities(row.get("core_entities")),
        "api_design": _api_design(row.get("api_design")),
        "data_flow": _strings(row.get("data_flow"), 8, item_limit=400),
        "high_level": _strings(row.get("high_level"), 8, item_limit=400),
        "deep_dives": _deep_dives(row.get("deep_dives")),
        "diagram": _diagram(row.get("diagram")),
        "trade_offs": items(row.get("trade_offs"), 4, item_limit=220),
        "follow_ups": items(row.get("follow_ups"), 3, item_limit=300),
        "interviewer_questions": _strings(row.get("interviewer_questions"), 5, item_limit=300),
        "questions_to_ask": _strings(row.get("questions_to_ask"), 4, item_limit=300),
        "grounded_in": text(row.get("grounded_in"), 160),
    }
    question["follow_ups_loaded"] = bool(question["follow_ups"])
    question["loaded_sections"] = loaded_sections(question)
    return question


def apply_section(
    question: dict[str, Any], section: str, payload: dict[str, Any], ctx: SkillContext
) -> dict[str, Any]:
    from .interviews import _api_design, _deep_dives, _diagram, _entities, _requirements, _strings

    row = dict(question)
    if section == "requirements":
        row["requirements"] = _requirements(payload.get("requirements"))
    elif section == "entities":
        row["core_entities"] = _entities(payload.get("core_entities"))
    elif section == "api":
        row["api_design"] = _api_design(payload.get("api_design"))
    elif section == "data_flow":
        row["data_flow"] = _strings(payload.get("data_flow"), 8, item_limit=400)
    elif section == "high_level":
        row["answer"] = clip_words(
            ground_text(strip_cliches(text(payload.get("answer"), 2500)), ctx), 200
        )
        row["high_level"] = _strings(payload.get("high_level"), 8, item_limit=400)
        row["diagram"] = _diagram(payload.get("diagram"))
        if payload.get("grounded_in"):
            row["grounded_in"] = text(payload.get("grounded_in"), 160)
    elif section == "deep_dives":
        row["deep_dives"] = _deep_dives(payload.get("deep_dives"))
        row["trade_offs"] = items(payload.get("trade_offs"), 4, item_limit=220)
    elif section == "questions":
        row["interviewer_questions"] = _strings(payload.get("interviewer_questions"), 5, item_limit=300)
        row["questions_to_ask"] = _strings(payload.get("questions_to_ask"), 4, item_limit=300)
    elif section == "follow_ups":
        row["follow_ups"] = items(payload.get("follow_ups"), 3, item_limit=300)
        row["follow_ups_loaded"] = True
    else:
        raise ValueError(f"unknown system design section: {section}")
    row["loaded_sections"] = loaded_sections(row)
    return row


def expand_question(
    ctx: SkillContext, question: dict[str, Any], section: str
) -> dict[str, Any]:
    """Write one subcomponent only, then merge it back into the question."""
    if section not in SYSTEM_DESIGN_SECTIONS and section != "follow_ups":
        raise ValueError(f"unknown system design section: {section}")
    prior = {
        key: question.get(key)
        for key in ("requirements", "core_entities", "api_design", "data_flow", "high_level", "deep_dives")
        if question.get(key)
    }
    messages = [
        ChatMessage(
            "system",
            system_prompt(
                "system_design_expand",
                f"Fill exactly one part of a system design interview answer: {section}. "
                f"{SECTION_INSTRUCTIONS[section]} "
                "Return only that section. Keep the same design decisions as the earlier sections. "
                "Use only facts from <job> and <portfolio>. Do not invent traffic, latency or cost numbers.",
            ),
        ),
        ChatMessage(
            "user",
            job_block(ctx, limit=3000)
            + "\n\n"
            + research_block(ctx, limit=1200)
            + "\n\n"
            + portfolio_block(ctx, limit=2500)
            + "\n\n<question>\n"
            + text(question.get("question"), 400)
            + "\n</question>\n\n<earlier_sections>\n"
            + json.dumps(prior, ensure_ascii=False)
            + "\n</earlier_sections>\n\nWrite the "
            + section
            + " JSON.",
        ),
    ]
    payload, _response = ctx.llm.complete_json(
        messages,
        section_schema(section),
        model=ctx.llm.model_for("large"),
        temperature=0.2,
        max_tokens=1800 if section in {"high_level", "deep_dives"} else 1000,
        attempts=2,
    )
    return apply_section(question, section, payload, ctx)
