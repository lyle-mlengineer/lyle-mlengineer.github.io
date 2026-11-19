"""Which job, run and skill is spending money right now.

Both ledgers (LLM calls and web searches) are written by provider wrappers that
have no idea who called them. The pipeline sets this context before each skill
executes, so a call can be attributed without threading ids through every skill.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class CallContext:
    job_id: int | None = None
    run_id: int | None = None
    skill: str | None = None


_CURRENT: contextvars.ContextVar[CallContext | None] = contextvars.ContextVar(
    "skipper_call_context", default=None
)


def current_call_context() -> CallContext | None:
    return _CURRENT.get()


@contextmanager
def call_context(
    *,
    job_id: int | None = None,
    run_id: int | None = None,
    skill: str | None = None,
) -> Iterator[CallContext]:
    """Attribute every provider call made inside the block to one step."""
    context = CallContext(job_id=job_id, run_id=run_id, skill=skill)
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)
