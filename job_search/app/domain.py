"""Domain constants: the vocabularies the database stores as strings.

Keeping them here (not in routes or templates) means a status the database can
hold is a status the app can explain.
"""

from __future__ import annotations

JOB_STATUSES: tuple[str, ...] = (
    "discovered",
    "reviewing",
    "preparing",
    "ready",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "withdrawn",
    "archived",
)

JOB_STATUS_LABELS: dict[str, str] = {
    "discovered": "Discovered",
    "reviewing": "Reviewing",
    "preparing": "Preparing",
    "ready": "Ready to send",
    "applied": "Applied",
    "interviewing": "Interviewing",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
    "archived": "Archived",
}

# Status changes the UI is allowed to make. Archiving is reversible from anywhere;
# everything else is a forward step (or an honest correction: applied -> ready,
# interviewing -> rejected, etc).
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "discovered": {"reviewing", "preparing", "archived"},
    "reviewing": {"preparing", "discovered", "archived"},
    "preparing": {"ready", "reviewing", "archived"},
    "ready": {"applied", "preparing", "archived"},
    "applied": {"interviewing", "rejected", "withdrawn", "ready", "archived"},
    "interviewing": {"offer", "rejected", "withdrawn", "archived"},
    "offer": {"archived"},
    "rejected": {"archived"},
    "withdrawn": {"archived"},
    "archived": set(JOB_STATUSES) - {"archived"},
}

ACTIVE_JOB_STATUSES: tuple[str, ...] = (
    "discovered",
    "reviewing",
    "preparing",
    "ready",
    "applied",
    "interviewing",
    "offer",
)

RUN_STATUSES: tuple[str, ...] = ("queued", "running", "succeeded", "failed", "cancelled", "interrupted")
RUN_TERMINAL: frozenset[str] = frozenset({"succeeded", "failed", "cancelled", "interrupted"})

RUN_STATUS_LABELS: dict[str, str] = {
    "queued": "Queued",
    "running": "Working",
    "succeeded": "Finished",
    "failed": "Failed",
    "cancelled": "Cancelled",
    "interrupted": "Interrupted",
}

STEP_STATUSES: tuple[str, ...] = ("pending", "running", "succeeded", "failed", "skipped")

ARTIFACT_KINDS: tuple[str, ...] = (
    "job_summary",
    "company_research",
    "cv_pdf",
    "cv_docx",
    "cover_letter_pdf",
    "cover_letter_docx",
    "email",
    "tell_me_about_yourself",
    "work_history",
    "proud_project",
    "technical_interview",
    "behavioral_interview",
)

ARTIFACT_LABELS: dict[str, str] = {
    "job_summary": "Summary",
    "company_research": "Company research",
    "cv_pdf": "CV (PDF)",
    "cv_docx": "CV (DOCX)",
    "cover_letter_pdf": "Cover letter (PDF)",
    "cover_letter_docx": "Cover letter (DOCX)",
    "email": "Application email",
    "tell_me_about_yourself": "Tell me about yourself",
    "work_history": "Work history",
    "proud_project": "Projects I'm proud of",
    "technical_interview": "Technical interview",
    "behavioral_interview": "Behavioural interview",
}

# Ordered skill manifest. Weights drive progress; `optional` skills may fail
# without failing the run.
SKILLS: tuple[dict, ...] = (
    {"name": "job_extraction", "weight": 2.0, "optional": False, "requires": ()},
    {"name": "job_summary", "weight": 1.0, "optional": False, "requires": ("job_extraction",)},
    {"name": "company_research", "weight": 3.0, "optional": True, "requires": ("job_extraction",)},
    {"name": "cv_writing", "weight": 3.0, "optional": False, "requires": ("job_extraction",)},
    {"name": "cover_letter", "weight": 2.0, "optional": False, "requires": ("job_extraction", "company_research")},
    {"name": "email_writing", "weight": 1.0, "optional": True, "requires": ("cover_letter",)},
    {"name": "tell_me_about_yourself", "weight": 1.0, "optional": True, "requires": ("job_extraction",)},
    {"name": "work_history", "weight": 1.0, "optional": True, "requires": ("job_extraction",)},
    {"name": "proud_project", "weight": 1.0, "optional": True, "requires": ("job_extraction",)},
    {"name": "technical_interview", "weight": 3.0, "optional": True, "requires": ("job_extraction",)},
    {"name": "behavioral_interview", "weight": 3.0, "optional": True, "requires": ("job_extraction",)},
)

SKILL_LABELS: dict[str, str] = {
    "job_extraction": "Reading the posting",
    "job_summary": "Summarising the role",
    "company_research": "Researching the company",
    "cv_writing": "Writing your CV",
    "cover_letter": "Writing the cover letter",
    "email_writing": "Drafting the email",
    "tell_me_about_yourself": "Preparing your introduction",
    "work_history": "Telling your work history",
    "proud_project": "Choosing your proudest projects",
    "technical_interview": "Prepping technical questions",
    "behavioral_interview": "Prepping behavioural questions",
}

STATUS_TONE: dict[str, str] = {
    "discovered": "neutral",
    "reviewing": "info",
    "preparing": "info",
    "ready": "success",
    "applied": "info",
    "interviewing": "warning",
    "offer": "success",
    "rejected": "danger",
    "withdrawn": "neutral",
    "archived": "muted",
}


def can_transition(current: str, target: str) -> bool:
    return target in STATUS_TRANSITIONS.get(current, set())


def step_by_name(name: str) -> dict:
    for step in SKILLS:
        if step["name"] == name:
            return step
    raise KeyError(name)
