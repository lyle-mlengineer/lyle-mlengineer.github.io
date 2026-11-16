import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models import Chunk, Document, Run
from app.pipeline.documents.errors import DocumentError
from app.pipeline.documents.extractor import extract_document_facts
from app.pipeline.documents.service import (
    count_active_documents,
    ingest_upload,
    list_documents,
    pin_document,
    record_failure,
)
from app.pipeline.resolve.schema import slot_for
from app.pipeline.resolve.service import ResolveError, build_gap_report
from app.schemas.documents import (
    ChunkOut,
    DocumentDetail,
    DocumentOut,
    DocumentReport,
    PinIn,
    UploadOut,
)
from app.schemas.profile import SiteProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/runs/{run_id}/documents", tags=["documents"])


def _run_or_404(run_id: str, user: CurrentUser, db: DbSession) -> Run:
    run = db.scalar(
        select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _document_or_404(run: Run, document_id: str, db: DbSession) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.run_id == run.id,
            Document.tenant_id == run.tenant_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _validate_gap(run: Run, gap_key: str | None) -> None:
    if gap_key is None:
        return
    if slot_for(gap_key) is None:
        raise HTTPException(status_code=422, detail=f"unknown gap key {gap_key!r}")
    if not run.profile_json:
        raise HTTPException(status_code=409, detail="analyze the site first")
    profile = SiteProfile.model_validate(run.profile_json)
    gap = next((item for item in profile.gaps if item.key == gap_key), None)
    if gap is None:
        raise HTTPException(
            status_code=422, detail=f"{gap_key} is not a gap for this run"
        )
    if gap.status == "resolved":
        raise HTTPException(status_code=409, detail=f"{gap_key} is already resolved")


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
def upload_documents(
    run_id: str,
    user: CurrentUser,
    db: DbSession,
    files: Annotated[list[UploadFile], File(description="PDF, DOCX, PPTX, MD, TXT, CSV or image")],
    gap_key: Annotated[str | None, Form()] = None,
    pin_to_brand: Annotated[bool, Form()] = False,
) -> UploadOut:
    settings = get_settings()
    run = _run_or_404(run_id, user, db)
    if not run.profile_json:
        raise HTTPException(status_code=409, detail="analyze the site first")
    _validate_gap(run, gap_key)

    if not files:
        raise HTTPException(status_code=422, detail="upload at least one file")
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=422,
            detail=f"at most {settings.max_upload_files} files per upload",
        )
    already = count_active_documents(db, run)
    if already + len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=422,
            detail=(
                f"at most {settings.max_upload_files} documents per run; "
                f"{already} already uploaded"
            ),
        )

    ready_ids: list[str] = []
    reports: list[DocumentReport] = []
    failures: list[str] = []
    failure_codes: list[int] = []
    limit = settings.max_document_bytes

    for upload in files:
        name = upload.filename or "upload"
        try:
            data = upload.file.read(limit + 1)
        except OSError as exc:
            message = f"{name}: could not read the upload ({exc})"
            failures.append(message)
            failure_codes.append(400)
            reports.append(
                DocumentReport(filename=name, status="failed", failures=[message])
            )
            continue

        if len(data) > limit:
            message = (
                f"{name}: file exceeds the {limit // (1024 * 1024)} MB limit"
            )
            document = record_failure(db, run, user.id, name, message)
            failures.append(message)
            failure_codes.append(413)
            reports.append(
                DocumentReport(
                    filename=document.filename,
                    document_id=document.id,
                    status="failed",
                    failures=[message],
                )
            )
            continue

        try:
            ingested = ingest_upload(
                db,
                run,
                user.id,
                name,
                data,
                pin_to_brand=pin_to_brand,
            )
        except DocumentError as exc:
            message = str(exc)
            document = record_failure(db, run, user.id, name, message)
            failures.append(message)
            failure_codes.append(exc.status_code)
            reports.append(
                DocumentReport(
                    filename=document.filename,
                    document_id=document.id,
                    status="failed",
                    failures=[message],
                )
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("document upload failed for %s", name)
            message = f"{name}: could not ingest the file ({type(exc).__name__})"
            document = record_failure(db, run, user.id, name, message)
            failures.append(message)
            failure_codes.append(500)
            reports.append(
                DocumentReport(
                    filename=document.filename,
                    document_id=document.id,
                    status="failed",
                    failures=[message],
                )
            )
            continue

        document = ingested.document
        ready_ids.append(document.id)
        reports.append(
            DocumentReport(
                filename=document.filename,
                document_id=document.id,
                status="ready",
                mime=document.mime,
                pages=document.pages,
                chunks=document.chunk_count,
            )
        )

    facts_extracted = 0
    if ready_ids:
        extraction = extract_document_facts(
            db,
            run,
            user.id,
            target_keys=[gap_key] if gap_key else None,
            document_ids=ready_ids,
        )
        facts_extracted = extraction.facts_extracted
        for report in reports:
            if report.document_id:
                report.extracted_facts = extraction.per_document.get(
                    report.document_id, 0
                )

    try:
        gaps = build_gap_report(db, run)
    except ResolveError as exc:
        db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()

    if not ready_ids:
        detail = "; ".join(failures) or "no document could be accepted"
        code = 413 if failure_codes and all(item == 413 for item in failure_codes) else 422
        raise HTTPException(status_code=code, detail=detail)

    return UploadOut(
        run_id=run.id,
        documents=reports,
        facts_extracted=facts_extracted,
        gaps=gaps,
    )


@router.get("", response_model=list[DocumentOut])
def get_documents(run_id: str, user: CurrentUser, db: DbSession) -> list[DocumentOut]:
    run = _run_or_404(run_id, user, db)
    return [DocumentOut.model_validate(item) for item in list_documents(db, run)]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    run_id: str, document_id: str, user: CurrentUser, db: DbSession
) -> DocumentDetail:
    run = _run_or_404(run_id, user, db)
    document = _document_or_404(run, document_id, db)
    chunks = db.scalars(
        select(Chunk)
        .where(
            Chunk.document_id == document.id,
            Chunk.run_id == run.id,
            Chunk.tenant_id == run.tenant_id,
        )
        .order_by(Chunk.ordinal)
    )
    payload = DocumentOut.model_validate(document).model_dump()
    return DocumentDetail(
        **payload, chunks=[ChunkOut.model_validate(chunk) for chunk in chunks]
    )


@router.post("/{document_id}/pin", response_model=DocumentOut)
def set_document_pin(
    run_id: str,
    document_id: str,
    body: PinIn,
    user: CurrentUser,
    db: DbSession,
) -> DocumentOut:
    run = _run_or_404(run_id, user, db)
    document = _document_or_404(run, document_id, db)
    if document.status != "ready":
        raise HTTPException(
            status_code=409, detail="only a parsed document can be pinned"
        )
    pin_document(db, run, user.id, document, body.pinned)
    db.commit()
    return DocumentOut.model_validate(document)
