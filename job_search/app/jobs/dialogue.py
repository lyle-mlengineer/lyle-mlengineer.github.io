"""Turn the interview pack into something two voices can read out loud.

The pack is already written: the LLM produced the questions, the answers and the
delivery notes. This module only decides who says what and how it should sound —
no new prose is generated, so nothing here can contradict the pack or invent
experience.

Delivery words come from two places: the notes the LLM wrote (``"slow down on
the metrics"`` becomes ``["measured"]``) and the shape of the question itself
(a warm-up is ``["relaxed"]``, a deep-dive is ``["measured"]``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..providers.tts.pricing import speech_cost

#: The questions the three spoken skills answer, in interview order.
SPOKEN_PROMPTS: dict[str, str] = {
    "tell_me_about_yourself": "To start, tell me about yourself.",
    "work_history": "Walk me through your work history.",
    "proud_project": "Tell me about a project you are proud of.",
}

#: Which delivery word a note is really asking for.
NOTE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "warm": ("warm", "friendly", "smile", "approachable", "human"),
    "steady": ("steady", "even", "slow", "pause", "unhurried", "breathe", "clear"),
    "confident": ("confident", "direct", "assertive", "firm", "own it"),
    "measured": ("measured", "precise", "technical", "careful", "detail", "trade-off"),
    "bright": ("bright", "energetic", "upbeat", "enthusiastic"),
    "thoughtful": ("thoughtful", "reflective", "consider", "thought"),
}

#: How an interviewer should ask versus how a candidate should answer.
INTERVIEWER_DIRECTION = ("neutral", "curious")
ANSWERER_DIRECTION = ("warm", "confident")

DIFFICULTY_DIRECTION: dict[str, tuple[str, ...]] = {
    "warm-up": ("relaxed", "warm"),
    "core": ("confident", "steady"),
    "deep": ("measured", "thoughtful"),
}

MAX_ANSWER_CHARS = 2_400


#: Every section of the pack that can be read out loud.
PACK_KINDS: tuple[str, ...] = (
    "tell_me_about_yourself",
    "work_history",
    "proud_project",
    "technical_interview",
    "system_design",
    "low_level_design",
    "coding",
    "behavioral_interview",
)


@dataclass(frozen=True)
class Turn:
    index: int
    role: str  # interviewer|interviewee
    section: str
    text: str
    kind: str = ""  # which interview-pack section the turn belongs to
    direction: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def direction_from_notes(notes: list[str] | None, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    """Map free-text delivery notes onto the small set of direction words."""
    words: list[str] = []
    for note in notes or []:
        lowered = str(note).lower()
        for word, triggers in NOTE_KEYWORDS.items():
            if word in words:
                continue
            if any(trigger in lowered for trigger in triggers):
                words.append(word)
            if len(words) == 2:
                return tuple(words)
    return tuple(words) if words else fallback


def build_turns(
    payloads: dict[str, dict[str, Any]],
    *,
    max_turns: int = 14,
    company: str | None = None,
    only: str | None = None,
) -> list[Turn]:
    """Build the interview, alternating interviewer and interviewee.

    Spoken answers come first because that is the order an interview opens in;
    the question banks follow with their strongest questions. ``only`` limits
    the plan to one pack section, which is how the per-section audio buttons
    generate just what the candidate asked for. The cap keeps a take to a
    listenable length — one take is minutes of audio, not an audiobook.
    """
    turns: list[Turn] = []

    def add(role: str, kind: str, section: str, text: str, direction: tuple[str, ...]) -> None:
        text = " ".join(str(text or "").split())
        if not text:
            return
        turns.append(
            Turn(
                index=len(turns),
                role=role,
                section=section,
                text=text[:MAX_ANSWER_CHARS],
                kind=kind,
                direction=direction,
            )
        )

    for kind, question in SPOKEN_PROMPTS.items():
        if only and kind != only:
            continue
        payload = payloads.get(kind) or {}
        answer = payload.get("answer")
        if not answer:
            continue
        section = question.rstrip(".")
        add("interviewer", kind, section, question, INTERVIEWER_DIRECTION)
        add(
            "interviewee",
            kind,
            section,
            answer,
            direction_from_notes(payload.get("delivery_notes"), fallback=ANSWERER_DIRECTION),
        )

    for kind, default_direction in (
        ("technical_interview", ("confident", "steady")),
        ("system_design", ("measured", "thoughtful")),
        ("low_level_design", ("measured", "thoughtful")),
        ("coding", ("steady", "thoughtful")),
        ("behavioral_interview", ("warm", "story")),
    ):
        if only and kind != only:
            continue
        payload = payloads.get(kind) or {}
        rows = payload.get("questions") or payload.get("problems") or []
        for row in rows:
            if len(turns) >= max_turns - 1:
                break
            question = (row or {}).get("question")
            answer = (row or {}).get("answer")
            if not question or not answer:
                continue
            section = str((row or {}).get("topic") or (row or {}).get("competency") or kind)
            difficulty = str((row or {}).get("difficulty") or "")
            add("interviewer", kind, section, question, INTERVIEWER_DIRECTION)
            add(
                "interviewee",
                kind,
                section,
                answer,
                DIFFICULTY_DIRECTION.get(difficulty, default_direction),
            )
        if len(turns) >= max_turns - 1:
            break

    return turns[:max_turns]


def payloads_from_artifacts(artifacts: list[Any]) -> dict[str, dict[str, Any]]:
    """Collect the current payload of every artifact that can be spoken."""
    wanted = set(SPOKEN_PROMPTS) | {
        "technical_interview",
        "system_design",
        "low_level_design",
        "coding",
        "behavioral_interview",
    }
    out: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        kind = getattr(artifact, "kind", None)
        if kind in wanted and getattr(artifact, "is_current", False):
            payload = (getattr(artifact, "meta_json", None) or {}).get("payload")
            if isinstance(payload, dict):
                out[kind] = payload
    return out


def total_chars(turns: list[Turn]) -> int:
    return sum(len(turn.text) for turn in turns)


def estimate_cost(turns: list[Turn], provider: str) -> float:
    return speech_cost(provider, total_chars(turns))


def summarise(turns: list[Turn]) -> dict[str, Any]:
    questions = sum(1 for turn in turns if turn.role == "interviewer")
    return {
        "turns": len(turns),
        "questions": questions,
        "chars": total_chars(turns),
        "seconds": _spoken_seconds(turns),
    }


def _spoken_seconds(turns: list[Turn], *, chars_per_second: float = 14.5) -> int:
    """A reading-time estimate, so the form can say how long a take will be."""
    return int(round(total_chars(turns) / chars_per_second))
