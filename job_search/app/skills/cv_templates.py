"""The portfolio's own CV templates, used as the quality bar for generated CVs.

``cv/_generate_cvs.py`` in the portfolio repository defines six role CVs. They
are rendered into ``data/cv_templates.json`` so the app can show the model the
closest one: its headline, summary, competency naming, metric-bearing bullets
and project prose. The model tailors that template to the posting; it does not
invent a new resume shape.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TEMPLATE_FILE = "cv_templates.json"
FALLBACK = "ml_engineer"

# Ordered: the first group with a hit wins, then the highest score.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ml_researcher": ("research scientist", "researcher", "research engineer", "phd", "publication"),
    "data_engineer": ("data engineer", "analytics engineer", "data platform", "etl", "warehouse"),
    "software_engineer": ("software engineer", "full-stack", "full stack", "backend", "frontend", "web engineer"),
    "ai_engineer": ("ai engineer", "applied ai", "agent engineer", "llm engineer", "generative ai", "genai"),
    "ai_ml_engineer": ("ai/ml", "ai-ml", "mlops engineer"),
}


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def choose_template(portfolio_dir: Path, role: str) -> tuple[str, dict[str, Any]]:
    """Pick the closest of the six portfolio CVs for this role."""
    candidates = (
        Path(portfolio_dir).parent / TEMPLATE_FILE,
        Path(__file__).resolve().parents[2] / "data" / TEMPLATE_FILE,
    )
    templates: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        templates = _load(str(candidate))
        if templates:
            break
    if not templates:
        return FALLBACK, {}
    title = " ".join(role.lower().split())
    for name, keywords in _KEYWORDS.items():
        if name in templates and any(keyword in title for keyword in keywords):
            return name, templates[name]
    if "machine learning" in title or "ml" in title.split():
        return "ml_engineer", templates.get("ml_engineer", {})
    return FALLBACK, templates.get(FALLBACK, {})


def template_prompt(portfolio_dir: Path, role: str) -> str:
    """A compact, JSON-safe view of the closest portfolio CV."""
    name, template = choose_template(portfolio_dir, role)
    if not template:
        return ""
    # Keys intentionally differ from the output schema: this is a wording and
    # emphasis reference, not a payload the model should copy verbatim.
    view = {
        "template": name,
        "headline": template.get("headline", ""),
        "summary_reference": template.get("summary", ""),
        "competency_areas": [
            {"name": item.get("name", ""), "reference": item.get("items", "")}
            for item in template.get("competencies", [])[:5]
        ],
        "technical_areas": [
            {"name": item.get("name", ""), "reference": item.get("items", "")}
            for item in template.get("tech", [])[:5]
        ],
        "experience_reference": template.get("jobs", [])[:4],
        "project_examples": template.get("projects", [])[:3],
        "education": template.get("education", []),
        "certifications": template.get("certifications", ""),
    }
    return json.dumps(view, ensure_ascii=False, indent=1)
