from __future__ import annotations

import json

from .base import Skill
from .cv_writing import CVWritingSkill
from .fixtures import FAKE_CV
from .job_extraction import JobExtractionSkill
from .job_summary import JobSummarySkill

SKILL_REGISTRY: dict[str, Skill] = {
    skill.name: skill for skill in (JobExtractionSkill(), JobSummarySkill(), CVWritingSkill())
}


def get_skill(name: str) -> Skill:
    try:
        return SKILL_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown skill: {name}") from exc


# The fake provider is the default in development. These responses make the
# first real pipeline run work end to end without a key, and give tests a
# deterministic extraction to assert on.
FAKE_RESPONSES: dict[str, str] = {
    "job_extraction": json.dumps(
        {
            "title": "Senior Machine Learning Engineer",
            "company_name": "Acme Speech",
            "company_domain": "acme.example",
            "location": "Remote (Europe)",
            "work_mode": "remote",
            "employment_type": "full-time",
            "seniority": "senior",
            "salary": {"min": 90000, "max": 120000, "currency": "EUR", "period": "year"},
            "responsibilities": [
                "Own speech recognition quality across six languages.",
                "Ship evaluation tooling used by the ML team.",
            ],
            "must_have": ["Python", "PyTorch", "speech recognition experience"],
            "nice_to_have": ["Whisper fine-tuning", "LoRA"],
            "keywords": ["ASR", "Whisper", "evaluation", "Python"],
            "benefits": ["Remote-first", "Learning budget"],
            "deadline": None,
            "summary_one_line": "Own ASR quality for a multilingual voice platform.",
            "red_flags": [],
        }
    ),
    "job_summary": json.dumps(
        {
            "one_liner": "A senior ASR role owning recognition quality for a multilingual voice platform.",
            "what_you_do": [
                "Own speech recognition quality across six languages.",
                "Build evaluation tooling the ML team relies on.",
            ],
            "what_they_want": [
                "Python and PyTorch in production.",
                "Hands-on speech recognition experience.",
            ],
            "why_it_matters": (
                "The role sits where model quality meets real users, so evaluation decisions "
                "change what customers hear."
            ),
            "fit_signals": [
                "Whisper fine-tuning and LoRA experience map to the stated stack.",
                "Evaluation tooling is a recurring theme in the portfolio.",
            ],
            "gaps": ["The posting does not state team size or on-call expectations."],
        }
    ),
    "cv_writing": json.dumps(FAKE_CV),
}
