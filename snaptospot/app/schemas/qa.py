"""Contracts for the quality report written next to every kit.

A gate is pass, fail or skip. ``skip`` is only used when the check cannot run on
this machine (no OCR engine, no Chromium); it is never used to hide a failure.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design import CardId

GateStatus = Literal["pass", "fail", "skip"]
GateAction = Literal["variant", "density", "skip"]


class GateFailure(BaseModel):
    """One concrete reason an asset did not pass a gate."""

    model_config = ConfigDict(extra="forbid")

    slot: str | None = None
    reason: str
    detail: str = ""


class GateResult(BaseModel):
    """The outcome of one check for one asset or for the whole kit."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: GateStatus
    method: str
    detail: str = ""
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    failures: list[GateFailure] = Field(default_factory=list)


class RetryPlan(BaseModel):
    """What to try after a failure: another variant, a denser card, or a skip."""

    model_config = ConfigDict(extra="forbid")

    action: GateAction
    detail: str
    template: str | None = None
    density: int | None = None


class AssetQa(BaseModel):
    """Per-asset status, the gate results, and the escalation if it failed."""

    model_config = ConfigDict(extra="forbid")

    asset: str
    platform: str
    card: str
    filename: str
    path: str
    width: int
    height: int
    sha256: str
    status: GateStatus
    gates: list[GateResult] = Field(default_factory=list)
    retry: RetryPlan | None = None


class QaSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    gates_run: int = 0


class QaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platforms: list[str] = Field(
        default_factory=lambda: [
            "linkedin",
            "x",
            "instagram",
            "whatsapp",
            "tiktok",
        ],
        max_length=8,
    )
    cards: list[CardId] = Field(
        default_factory=lambda: ["hero", "capabilities", "projects", "proof"],
        max_length=4,
    )
    reuse_cache: bool = True
    use_ocr: bool = True


class QaOut(BaseModel):
    """``qa.json``: the report returned with the kit and stored on disk."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    version: int = 1
    generated_at: datetime
    renderer_version: str
    template_version: str
    path: str
    assets: list[AssetQa] = Field(default_factory=list)
    kit_gates: list[GateResult] = Field(default_factory=list)
    summary: QaSummary
    warnings: list[str] = Field(default_factory=list)
