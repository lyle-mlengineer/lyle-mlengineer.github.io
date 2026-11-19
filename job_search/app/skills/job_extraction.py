"""Skill 1 — turn an untrusted posting into structured fields."""

from __future__ import annotations

import re
from typing import Any

from ..providers.llm.base import ChatMessage
from ..utils import clean_text, normalize_company
from .base import GROUND_RULES, Skill, SkillContext, job_block

_WORK_MODES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on-site": "onsite",
    "onsite": "onsite",
    "office": "onsite",
}
_EMPLOYMENT = {
    "full-time": "full-time",
    "full time": "full-time",
    "part-time": "part-time",
    "part time": "part-time",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
}
_SENIORITY = {
    "intern": "intern",
    "junior": "junior",
    "mid": "mid",
    "mid-level": "mid",
    "senior": "senior",
    "staff": "staff",
    "principal": "principal",
    "lead": "lead",
    "director": "director",
}
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class JobExtractionSkill(Skill):
    name = "job_extraction"
    tier = "large"
    output_kind = "internal"
    weight = 2.0
    max_tokens = 2_800

    def schema(self) -> dict[str, Any]:
        strings = {"type": "array", "items": {"type": "string", "max_len": 400}}
        return {
            "type": "object",
            "required": ["title", "company_name", "responsibilities", "must_have", "keywords"],
            "properties": {
                "title": {"type": "string", "min_len": 2, "max_len": 200},
                "company_name": {"type": "string", "min_len": 1, "max_len": 200},
                "company_domain": {"type": "string", "max_len": 200, "nullable": True},
                "location": {"type": "string", "max_len": 200, "nullable": True},
                "work_mode": {
                    "type": "string",
                    "enum": ["remote", "hybrid", "onsite", "unknown"],
                    "nullable": True,
                },
                "employment_type": {"type": "string", "max_len": 40, "nullable": True},
                "seniority": {"type": "string", "max_len": 40, "nullable": True},
                "responsibilities": strings,
                "must_have": strings,
                "nice_to_have": strings,
                "keywords": strings,
                "benefits": strings,
                "deadline": {"type": "string", "max_len": 20, "nullable": True},
                "summary_one_line": {"type": "string", "max_len": 400, "nullable": True},
                "red_flags": strings,
                "salary": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "min": {"type": "integer", "nullable": True},
                        "max": {"type": "integer", "nullable": True},
                        "currency": {"type": "string", "max_len": 8, "nullable": True},
                        "period": {"type": "string", "max_len": 20, "nullable": True},
                    },
                },
            },
        }

    def build_messages(self, ctx: SkillContext) -> list[ChatMessage]:
        return [
            ChatMessage(
                "system",
                GROUND_RULES
                + "\nSKILL: job_extraction\n"
                + "Extract only what the posting states. Unknown fields are null. Do not guess a company "
                + "domain from the company name; use the URL host only when it is clearly the employer.",
            ),
            ChatMessage("user", job_block(ctx)),
        ]

    def postprocess(self, payload: dict[str, Any], ctx: SkillContext) -> dict[str, Any]:
        data = dict(payload)
        data["title"] = clean_text(str(data.get("title") or ctx.job.title))[:200] or ctx.job.title
        data["company_name"] = normalize_company(str(data.get("company_name") or ""))
        data["location"] = _optional(data.get("location"), 200)
        data["work_mode"] = _enum(data.get("work_mode"), _WORK_MODES)
        data["employment_type"] = _enum(data.get("employment_type"), _EMPLOYMENT)
        data["seniority"] = _enum(data.get("seniority"), _SENIORITY)
        for key in (
            "responsibilities",
            "must_have",
            "nice_to_have",
            "keywords",
            "benefits",
            "red_flags",
        ):
            data[key] = _list(data.get(key))
        data["keywords"] = list(dict.fromkeys(word.lower() for word in data["keywords"]))[:20]
        data["deadline"] = _date(data.get("deadline"))
        data["summary_one_line"] = _optional(data.get("summary_one_line"), 400)
        data["company_domain"] = _domain(data.get("company_domain"))
        data["salary"] = _salary(data.get("salary"))
        return data


def _optional(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = clean_text(str(value))[:limit]
    return text or None


def _enum(value: Any, mapping: dict[str, str]) -> str | None:
    text = clean_text(str(value or "")).lower()
    if text in {"", "unknown", "none", "null"}:
        return None
    return mapping.get(text, text[:40])


def _list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: list[str] = []
    for item in value:
        text = clean_text(str(item))[:400]
        if text and text not in seen:
            seen.append(text)
    return seen[:limit]


def _date(value: Any) -> str | None:
    text = clean_text(str(value or ""))
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    return match.group(0) if match else None


def _domain(value: Any) -> str | None:
    text = clean_text(str(value or "")).lower()
    text = re.sub(r"^https?://", "", text).split("/")[0].strip(".")
    return text[:200] or None


def _salary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    minimum = _int(value.get("min"))
    maximum = _int(value.get("max"))
    currency = clean_text(str(value.get("currency") or "")).upper()
    currency = currency if _CURRENCY.match(currency) else None
    period = _enum(value.get("period"), {"year": "year", "annual": "year", "month": "month", "day": "day", "hour": "hour"})
    if minimum is None and maximum is None and not currency:
        return None
    if minimum is not None and maximum is not None and maximum < minimum:
        minimum, maximum = maximum, minimum
    return {"min": minimum, "max": maximum, "currency": currency, "period": period}


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else None
