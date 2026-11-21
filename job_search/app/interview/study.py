"""Generate practice questions and find answers from uploaded interview sources.

Two entry points share one prompt shape:

* ``generate_questions`` writes a set of questions and model answers. It samples
  source chunks at random (or uses all of them for a single source) and adds a
  random angle, so two sets on the same material are different drills rather
  than a copy of the pack.
* ``answer_question`` retrieves the chunks that match a typed question (BM25,
  same FTS5 index) and asks for one answer with citations back to the source.

Both are now-or-never calls: the route reports the failure and the user can retry.
Nothing is written unless the model returned a usable payload.
"""

from __future__ import annotations

import random
from typing import Any

from ..config import Settings
from ..jobs.prompts import corpus_text, sanitize_untrusted, system_prompt, untrusted
from ..models import InterviewQuestion, Job
from ..providers.call_context import call_context
from ..providers.llm.base import ChatMessage, LLMProvider, LLMProviderError, SkillValidationError
from .sources import (
    SourceChunk,
    as_context,
    sample_source_chunks,
    save_questions,
    search_source_chunks,
)

PRACTICE_ANGLES: tuple[str, ...] = (
    "production debugging",
    "trade-offs and failure modes",
    "evaluation and measurement",
    "data modelling",
    "concurrency and backpressure",
    "API and interface design",
    "testing strategy",
    "cost and latency budgets",
    "security and untrusted input",
    "scaling one service without a rewrite",
)

QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["topic", "difficulty", "question", "answer"],
                "properties": {
                    "topic": {"type": "string", "max_len": 120},
                    "difficulty": {"type": "string", "enum": ["warm-up", "core", "deep"]},
                    "question": {"type": "string", "max_len": 500},
                    "answer": {"type": "string", "max_len": 3000},
                    "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
                    "source": {"type": "string", "max_len": 200},
                },
            },
        }
    },
}

FOLLOW_UP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["answers"],
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["question", "answer"],
                "properties": {
                    "question": {"type": "string", "max_len": 300},
                    "answer": {"type": "string", "max_len": 2000},
                },
            },
        }
    },
}

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["answer"],
    "properties": {
        "answer": {"type": "string", "max_len": 4000},
        "follow_ups": {"type": "array", "items": {"type": "string", "max_len": 300}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}


#: The seven interview subjects the Ask workspace offers, keyed by the value the
#: browser posts and labelled the way the page and the saved rows show them.
ASK_TOPICS: dict[str, str] = {
    "technical": "Technical",
    "system": "System design",
    "low_level": "Low-level design",
    "coding": "Coding",
    "behavioural": "Behavioural",
    "work_history": "Work history",
    "about": "About yourself",
}

#: One shape per subject, so two questions on different subjects do not come back
#: as the same generic paragraph. Everything below stays inside the untrusted
#: rules: the guidance is instruction, the facts still come from <portfolio>.
ASK_GUIDANCE: dict[str, str] = {
    "technical": (
        "Shape it as a technical interview answer: define the mechanism precisely, explain how it "
        "works underneath, say where you have used it in production, and name one trade-off."
    ),
    "system": (
        "Shape it as a system design answer: state the requirements and the scale you assume, sketch "
        "the components and the request/data flow, then cover the bottlenecks, failure modes and the "
        "trade-offs you chose."
    ),
    "low_level": (
        "Shape it as a low-level design answer: name the classes, interfaces and data structures, who "
        "owns the state, how concurrency and errors are handled, and how it is tested."
    ),
    "coding": (
        "Shape it as a coding interview answer: state the approach and its complexity first, then the "
        "steps in order, the edge cases, and the code-level detail that shows you have written it."
    ),
    "behavioural": (
        "Shape it as a behavioural answer in STAR order — situation, task, action, result — drawn only "
        "from <portfolio>, and finish with what you took from it."
    ),
    "work_history": (
        "Shape it as a walk through of your work history for the role or period asked about, using only "
        "<portfolio>: the scope, the team, what you personally owned and the measured outcome."
    ),
    "about": (
        "Shape it as a ninety-second 'tell me about yourself': where you started, the through-line, the "
        "strongest current proof, and why this role — using only <portfolio>."
    ),
}


def ask_topic(value: str | None) -> str:
    """Normalise a posted subject to a known key (``technical`` when unknown)."""
    key = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return key if key in ASK_TOPICS else "technical"


class StudyError(RuntimeError):
    """The practice call could not produce something worth showing."""


def _job_block(
    job: Job | None,
    company: str | None = None,
    *,
    role: str = "",
    level: str = "",
) -> str:
    if job is None:
        target = sanitize_untrusted(role.strip()[:120], limit=120) or "machine-learning engineer"
        seniority = sanitize_untrusted(level.strip()[:40], limit=40) or "senior"
        return (
            "<job>\nNo specific posting is open. Write interview practice questions "
            f"for a {seniority} {target}.\n</job>"
        )
    return (
        "<job>\n"
        f"Title: {job.title}\n"
        f"Company: {company or 'unknown'}\n"
        f"Seniority: {job.seniority or 'unknown'}\n\n"
        f"{sanitize_untrusted(job.raw_text, limit=8_000)}\n"
        "</job>"
    )


def _difficulty_instruction(difficulty: str) -> str:
    if difficulty in {"warm-up", "core", "deep"}:
        return f"Every question must be {difficulty} level."
    return (
        "Mix the levels: at least two warm-ups, the rest core, and one or two deep. "
        "Set the difficulty field truthfully."
    )


def _normalise_questions(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("questions") or []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()[:1_000]
        answer = str(item.get("answer") or "").strip()[:6_000]
        if not question or not answer:
            continue
        rows.append(
            {
                "topic": str(item.get("topic") or "General").strip()[:120],
                "difficulty": item.get("difficulty")
                if item.get("difficulty") in {"warm-up", "core", "deep"}
                else "core",
                "question": question,
                "answer": answer,
                "follow_ups": [
                    str(value).strip()[:300]
                    for value in (item.get("follow_ups") or [])
                    if str(value).strip()
                ][:4],
                "source": str(item.get("source") or "").strip()[:200],
            }
        )
    return rows[:limit]


def _context_chunks(
    db,
    source_ids: list[int] | None,
    *,
    seed: int | None,
    count: int = 8,
) -> list[SourceChunk]:
    rng = random.Random(seed)
    return sample_source_chunks(db, source_ids, count=count, rng=rng)


def generate_questions(
    db,
    settings: Settings,
    llm: LLMProvider,
    *,
    job: Job | None,
    company: str | None = None,
    source_ids: list[int] | None = None,
    source_id: int | None = None,
    count: int = 8,
    difficulty: str = "mixed",
    focus: str = "",
    seed: int | None = None,
    origin: str = "practice",
    role: str = "",
    level: str = "",
) -> list[InterviewQuestion]:
    """Generate and persist a practice set."""
    count = max(1, min(12, count))
    difficulty = difficulty if difficulty in {"mixed", "warm-up", "core", "deep"} else "mixed"
    chunks = _context_chunks(db, source_ids, seed=seed, count=max(6, count))

    if source_ids and not chunks:
        raise StudyError("Those sources have no readable text to generate from. Add a source first.")

    rng = random.Random(seed)
    angle = focus.strip()[:120] or rng.choice(PRACTICE_ANGLES)
    source_block = (
        untrusted("sources", as_context(chunks), source="uploaded interview sources")
        if chunks
        else "<sources>\nNo uploaded sources were selected. Use the job posting and portfolio only.\n</sources>"
    )
    portfolio = untrusted(
        "portfolio",
        corpus_text(str(settings.portfolio_dir)),
        source="portfolio corpus",
        limit=7_000,
    )

    messages = [
        ChatMessage(
            "system",
            system_prompt(
                "interview_practice",
                "Write interview practice questions with model answers. Each answer is 120–220 words, "
                "spoken first person when it is Lyle answering, and names a concrete decision or trade-off. "
                "Ground technical facts in <sources> or the posting. Ground claims about Lyle only in "
                "<portfolio>. If the sources do not cover a topic, ask a question they do cover. Never "
                "invent projects, employers, numbers or metrics. Return only the JSON object.",
            ),
        ),
        ChatMessage(
            "user",
            _job_block(job, company, role=role, level=level)
            + "\n\n"
            + source_block
            + "\n\n"
            + portfolio
            + f"\n\nWrite {count} questions on the angle: {angle}.\n"
            + _difficulty_instruction(difficulty)
            + "\nFor each question add one or two follow-ups and name the source it came from when it did.",
        ),
    ]

    try:
        with call_context(job_id=job.id if job else None, skill="interview_practice"):
            payload, response = llm.complete_json(
                messages,
                QUESTION_SCHEMA,
                model=llm.model_for("large"),
                temperature=0.5,
                max_tokens=6_000,
                attempts=2,
            )
    except (LLMProviderError, SkillValidationError) as exc:
        raise StudyError(f"The practice set could not be written: {exc}") from exc

    rows = _normalise_questions(payload, count)
    if not rows:
        raise StudyError("The model returned no usable questions. Try a different angle or source.")
    citations = [chunk.citation for chunk in chunks[:4]]
    for row in rows:
        row["citations"] = citations
    return save_questions(
        db,
        rows,
        job_id=job.id if job else None,
        source_id=source_id,
        origin=origin,
        model=response.model,
        role=role.strip()[:120] or None,
        level=level.strip()[:40] or None,
    )


def answer_follow_ups(
    db,
    settings: Settings,
    llm: LLMProvider,
    *,
    job: Job | None,
    company: str | None,
    question: str,
    answer: str,
    follow_ups: list[str],
    source_ids: list[int] | None = None,
    role: str = "",
    level: str = "",
) -> list[dict[str, str]]:
    """Write one short spoken answer for each follow-up beneath a question."""
    prompts = [" ".join(str(item).split())[:300] for item in follow_ups if str(item).strip()][:4]
    if not prompts:
        raise StudyError("This question has no follow-ups to answer.")

    query = " ".join([question, *prompts])
    chunks = search_source_chunks(db, query, source_ids=source_ids, limit=6, max_chars=6_000)
    source_block = (
        untrusted("sources", as_context(chunks), source="uploaded interview sources")
        if chunks
        else "<sources>\nNo uploaded source matched these follow-ups.\n</sources>"
    )
    portfolio = untrusted(
        "portfolio",
        corpus_text(str(settings.portfolio_dir)),
        source="portfolio corpus",
        limit=5_000,
    )
    numbered = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(prompts))
    messages = [
        ChatMessage(
            "system",
            system_prompt(
                "interview_follow_ups",
                "Answer each follow-up as Lyle would say it out loud in an interview: direct, specific "
                "and 50-120 words each. Stay consistent with <parent_answer>. Use <sources> for technical "
                "explanation and <portfolio> for Lyle's own experience. If the material does not support "
                "a claim, say what you would do or how you would reason instead of inventing facts or "
                "numbers. Keep the follow-ups in the order given. Return one JSON object with an answers "
                "array; each item has the question and its answer.",
            ),
        ),
        ChatMessage(
            "user",
            _job_block(job, company)
            + "\n\n"
            + source_block
            + "\n\n"
            + portfolio
            + f"\n\n<question>{sanitize_untrusted(question, limit=600)}</question>"
            + f"\n\n<parent_answer>{sanitize_untrusted(answer, limit=4_000)}</parent_answer>"
            + f"\n\n<follow_ups>\n{numbered}\n</follow_ups>\n"
            "Answer every follow-up in order.",
        ),
    ]

    try:
        with call_context(job_id=job.id if job else None, skill="interview_follow_up"):
            payload, _response = llm.complete_json(
                messages,
                FOLLOW_UP_SCHEMA,
                model=llm.model_for("large"),
                temperature=0.3,
                max_tokens=4_000,
                attempts=2,
            )
    except (LLMProviderError, SkillValidationError) as exc:
        raise StudyError(f"Those answers could not be written: {exc}") from exc

    rows = payload.get("answers") if isinstance(payload.get("answers"), list) else []
    answers: list[dict[str, str]] = []
    for index, prompt in enumerate(prompts):
        row = rows[index] if index < len(rows) and isinstance(rows[index], dict) else {}
        text = str(row.get("answer") or "").strip()
        if text:
            answers.append({"question": prompt, "answer": text[:2_000]})
    if not answers:
        raise StudyError("The model returned no usable follow-up answers. Try again.")
    return answers


def answer_question(
    db,
    settings: Settings,
    llm: LLMProvider,
    *,
    job: Job | None,
    company: str | None,
    question: str,
    source_ids: list[int] | None = None,
    topic: str = "",
    role: str = "",
    level: str = "",
) -> dict[str, Any]:
    """Find one answer, grounded in the matching source chunks.

    With no job the answer is written for the topic and target role instead, which
    is what the Ask workspace uses: the same retrieval and the same fields, only the
    shape of the answer changes.
    """
    question = (question or "").strip()
    if len(question) < 5:
        raise StudyError("Type a question first.")

    chunks = search_source_chunks(db, question, source_ids=source_ids, limit=8, max_chars=7_000)
    if not chunks:
        chunks = _context_chunks(db, source_ids, seed=None, count=6)

    source_block = (
        untrusted("sources", as_context(chunks), source="uploaded interview sources")
        if chunks
        else "<sources>\nNo uploaded sources were selected or matched this question.\n</sources>"
    )
    portfolio = untrusted(
        "portfolio",
        corpus_text(str(settings.portfolio_dir)),
        source="portfolio corpus",
        limit=6_000,
    )
    guidance = ASK_GUIDANCE.get(topic, "")
    messages = [
        ChatMessage(
            "system",
            system_prompt(
                "interview_answer",
                "Answer the interview question directly, in the first person as Lyle would say it out loud. "
                "Use <sources> for technical explanation and <portfolio> for Lyle's own experience. If the "
                "material does not cover the question, say so plainly and give the structure of a good "
                "answer instead of inventing facts, numbers or employers. Keep it under 260 words. Return "
                "one JSON object with answer, follow_ups and confidence."
                + (f"\n{guidance}" if guidance else ""),
            ),
        ),
        ChatMessage(
            "user",
            _job_block(job, company, role=role, level=level)
            + "\n\n"
            + source_block
            + "\n\n"
            + portfolio
            + f"\n\n<question>{sanitize_untrusted(question, limit=600)}</question>\n"
            "Answer this question.",
        ),
    ]

    try:
        with call_context(job_id=job.id if job else None, skill="interview_answer"):
            payload, response = llm.complete_json(
                messages,
                ANSWER_SCHEMA,
                model=llm.model_for("large"),
                temperature=0.3,
                max_tokens=3_000,
                attempts=2,
            )
    except (LLMProviderError, SkillValidationError) as exc:
        raise StudyError(f"That answer could not be written: {exc}") from exc

    answer = str(payload.get("answer") or "").strip()
    if not answer:
        raise StudyError("The model returned an empty answer. Try again.")
    return {
        "question": question,
        "answer": answer[:6_000],
        "follow_ups": [
            str(item).strip()[:300]
            for item in (payload.get("follow_ups") or [])
            if str(item).strip()
        ][:4],
        "confidence": payload.get("confidence")
        if payload.get("confidence") in {"high", "medium", "low"}
        else "medium",
        "citations": list(dict.fromkeys(chunk.citation for chunk in chunks[:5])),
        "model": response.model,
    }
