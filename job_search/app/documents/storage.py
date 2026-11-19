"""Versioned artifact storage on disk plus the artifact rows in SQLite."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Artifact, Company, Job, JobEvent, Run
from .cv_docx import build_cv_docx
from .cv_pdf import render_pdf
from .resume import artifact_filename

logger = logging.getLogger("skipper.documents")

CV_KINDS = ("cv_pdf", "cv_docx")


def save_cv_bundle(
    db: Session,
    job: Job,
    run: Run,
    resume: dict[str, Any],
    settings: Settings,
) -> tuple[Artifact, Artifact]:
    """Render both formats at one version, flip ``is_current`` and persist metadata."""
    docx_bytes = build_cv_docx(resume)
    pdf = render_pdf(docx_bytes, resume, soffice_path=settings.soffice_path)

    latest = db.scalar(
        select(func.max(Artifact.version)).where(
            Artifact.job_id == job.id, Artifact.kind.in_(CV_KINDS)
        )
    )
    version = (latest or 0) + 1
    company_row = db.get(Company, job.company_id) if job.company_id else None
    company = company_row.name if company_row else None
    folder = Path(settings.artifacts_dir) / f"job-{job.id}"
    folder.mkdir(parents=True, exist_ok=True)

    db.execute(
        update(Artifact)
        .where(Artifact.job_id == job.id, Artifact.kind.in_(CV_KINDS))
        .values(is_current=False)
    )

    artifacts: list[Artifact] = []
    for kind, content, extension in (
        ("cv_pdf", pdf.content, "pdf"),
        ("cv_docx", docx_bytes, "docx"),
    ):
        name = artifact_filename(company, job.title, version, extension)
        path = folder / name
        path.write_bytes(content)
        meta = {
            "download_name": name,
            "resume": resume,
            "pdf_engine": pdf.engine,
            "pages": pdf.pages,
        }
        artifact = Artifact(
            job_id=job.id,
            run_id=run.id,
            kind=kind,
            version=version,
            is_current=True,
            format=extension,
            path=str(path),
            bytes=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            meta_json=meta,
        )
        db.add(artifact)
        artifacts.append(artifact)

    if pdf.pages > 2:
        logger.warning("cv for job %s is %s pages", job.id, pdf.pages)
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="artifact",
                note=f"CV v{version} is {pdf.pages} pages; trim it before sending.",
                run_id=run.id,
            )
        )
    db.add(JobEvent(job_id=job.id, event_type="artifact", note=f"Created tailored CV v{version}", run_id=run.id))
    db.flush()
    return artifacts[0], artifacts[1]


def artifact_file(artifact: Artifact, settings: Settings) -> Path | None:
    """Resolve an artifact path, refusing anything outside the artifacts directory."""
    if not artifact.path:
        return None
    root = Path(settings.artifacts_dir).resolve()
    try:
        path = Path(artifact.path).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        logger.warning("artifact %s points outside the artifacts directory", artifact.id)
        return None
    return path if path.is_file() else None


def download_name(artifact: Artifact) -> str:
    meta = artifact.meta_json or {}
    name = str(meta.get("download_name") or "").strip()
    if name:
        return name
    return Path(artifact.path or f"artifact-{artifact.id}.{artifact.format}").name
