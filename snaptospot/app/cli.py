import argparse
import hashlib
import json
import sys
from pathlib import Path

from app.config import get_settings
from app.pipeline.extract import extract_content
from app.pipeline.ingest.crawl import crawl_site
from app.pipeline.ingest.errors import CrawlError
from app.pipeline.ingest.profile import build_profile
from app.pipeline.understand import enrich_understanding


def _ingest(url: str, out: str | None, max_pages: int | None) -> int:
    settings = get_settings()
    slug = hashlib.sha256(url.encode()).hexdigest()[:10]  # noqa: S324
    artifact_dir = Path(settings.media_root) / "cli" / slug
    try:
        crawl = crawl_site(url, max_pages=max_pages, artifact_dir=artifact_dir)
    except CrawlError as exc:
        print(f"crawl failed: {exc}", file=sys.stderr)
        return 1

    profile = build_profile(crawl)
    profile.understanding = enrich_understanding(profile)
    payload = profile.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False)

    if out:
        destination = Path(out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        print(
            f"wrote {out}: {profile.observed.page_count} pages, "
            f"{profile.observed.asset_count} assets",
            file=sys.stderr,
        )
    else:
        print(text)

    if profile.observed.page_count < 1:
        return 1
    return 0


def _extract(url: str, out: str | None, max_pages: int | None) -> int:
    settings = get_settings()
    slug = hashlib.sha256(url.encode()).hexdigest()[:10]  # noqa: S324
    artifact_dir = Path(settings.media_root) / "cli" / slug
    try:
        crawl = crawl_site(url, max_pages=max_pages, artifact_dir=artifact_dir)
    except CrawlError as exc:
        print(f"crawl failed: {exc}", file=sys.stderr)
        return 1

    profile = build_profile(crawl)
    profile.understanding = enrich_understanding(profile)
    extraction = extract_content(profile)
    payload = {
        "content_model": extraction.content_model.model_dump(mode="json"),
        "rejected": [item.model_dump(mode="json") for item in extraction.rejected],
        "conflicts": extraction.conflicts,
        "signals": extraction.signals,
        "gaps": [gap.model_dump(mode="json", by_alias=True) for gap in profile.gaps],
        "model_versions": extraction.model_versions,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)

    if out:
        destination = Path(out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        print(
            f"wrote {out}: {len(extraction.content_model.facts)} facts, "
            f"{len(extraction.rejected)} rejected, {len(profile.gaps)} gaps",
            file=sys.stderr,
        )
    else:
        print(text)

    return 0


def _expire_documents(retention_days: int | None, tenant_id: str | None) -> int:
    from app.db import SessionLocal
    from app.pipeline.documents.expiry import expire_documents

    with SessionLocal() as db:
        report = expire_documents(
            db, tenant_id=tenant_id, retention_days=retention_days
        )
        db.commit()
    print(
        f"expired {report.expired} document(s), deleted {report.files_deleted} file(s)",
        file=sys.stderr,
    )
    return 0


def _render(run_id: str, platforms: list[str], cards: list[str], force: bool) -> int:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Run
    from app.render.service import RenderError, render_run
    from app.schemas.render import RenderIn

    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            print(f"run not found: {run_id}", file=sys.stderr)
            return 1
        try:
            report = render_run(
                db,
                run,
                RenderIn(
                    platforms=platforms,
                    cards=cards,  # type: ignore[arg-type]
                    reuse_cache=not force,
                ),
            )
        except RenderError as exc:
            print(f"render failed: {exc}", file=sys.stderr)
            return 1
        db.commit()

    for asset in report.assets:
        print(
            f"{asset.asset} -> {asset.path} "
            f"({asset.width}x{asset.height}, {asset.size} bytes, {asset.sha256[:12]})"
        )
    return 0


def _video(
    run_id: str,
    platforms: list[str],
    force: bool,
    workers: int,
) -> int:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Run
    from app.render.video import VideoError, render_run_videos
    from app.schemas.video import VideoIn

    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            print(f"run not found: {run_id}", file=sys.stderr)
            return 1
        try:
            report = render_run_videos(
                db,
                run,
                VideoIn(
                    platforms=platforms,
                    reuse_cache=not force,
                    workers=workers,
                ),
            )
        except VideoError as exc:
            print(f"video failed: {exc}", file=sys.stderr)
            return 1
        db.commit()

    for item in report.videos:
        print(
            f"{item.platform}/{item.filename} -> {item.path} "
            f"({item.width}x{item.height}, {item.duration:g}s, {item.bytes} bytes, "
            f"{item.sha256[:12]})"
        )
        print(f"  poster {item.poster_filename} -> {item.poster_path} ({item.poster_bytes} bytes)")
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


def _copy(run_id: str, platforms: list[str], use_llm: bool) -> int:
    from sqlalchemy import select

    from app.copy.deck import CopyValidationError
    from app.copy.service import CopyError, copy_run
    from app.db import SessionLocal
    from app.models import Run
    from app.schemas.copy import CopyIn

    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            print(f"run not found: {run_id}", file=sys.stderr)
            return 1
        try:
            report = copy_run(
                db,
                run,
                CopyIn(platforms=platforms, use_llm=use_llm),
            )
        except (CopyError, CopyValidationError) as exc:
            print(f"copy failed: {exc}", file=sys.stderr)
            return 1
        db.commit()

    for item in report.files:
        print(
            f"{item.platform}/post.md -> {item.path} "
            f"({item.primary_chars} chars, {len(item.hashtags)} hashtags, "
            f"{item.source}, {item.sha256[:12]})"
        )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


def _qa(
    run_id: str,
    platforms: list[str] | None,
    cards: list[str] | None,
    use_ocr: bool,
) -> int:
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Run
    from app.qa.service import QaError, run_qa
    from app.schemas.qa import QaIn

    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if run is None:
            print(f"run not found: {run_id}", file=sys.stderr)
            return 1
        body = QaIn(use_ocr=use_ocr)
        if platforms:
            body = body.model_copy(update={"platforms": platforms})
        if cards:
            body = body.model_copy(update={"cards": cards})  # type: ignore[arg-type]
        try:
            report = run_qa(db, run, body)
        except QaError as exc:
            print(f"qa failed: {exc}", file=sys.stderr)
            return 1
        db.commit()

    for asset in report.assets:
        print(f"{asset.asset}: {asset.status} ({len(asset.gates)} gates)")
        for gate in asset.gates:
            if gate.status == "fail":
                reason = gate.failures[0].detail if gate.failures else gate.detail
                print(f"  FAIL {gate.name}: {reason}")
            elif gate.status == "skip":
                print(f"  skip {gate.name}: {gate.detail}")
        if asset.retry is not None:
            print(f"  retry {asset.retry.action}: {asset.retry.detail}")
    for gate in report.kit_gates:
        print(f"kit/{gate.name}: {gate.status}")
        for failure in gate.failures:
            print(f"  FAIL {failure.slot or '-'}: {failure.detail}")
    summary = report.summary
    print(
        f"qa.json -> {Path(get_settings().media_root) / report.path} "
        f"({summary.passed} passed, {summary.failed} failed, "
        f"{summary.skipped} skipped)"
    )
    return 1 if summary.failed or any(g.status == "fail" for g in report.kit_gates) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snaptospot", description="SnapToSpot tools")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="crawl a site and print its SiteProfile")
    ingest.add_argument("url")
    ingest.add_argument("--out", help="write the profile to a JSON file")
    ingest.add_argument("--max-pages", type=int, default=None)

    extract = sub.add_parser("extract", help="crawl a site and print its ContentModel")
    extract.add_argument("url")
    extract.add_argument("--out", help="write the content model to a JSON file")
    extract.add_argument("--max-pages", type=int, default=None)

    expire = sub.add_parser(
        "expire-documents", help="delete document chunks and files past retention"
    )
    expire.add_argument(
        "--days",
        type=int,
        default=None,
        help="override retention by age; default uses each document's expires_at",
    )
    expire.add_argument("--tenant", default=None, help="limit to one tenant id")

    render = sub.add_parser(
        "render", help="render a composed run's stills to PNG"
    )
    render.add_argument("--run", required=True, help="run id")
    render.add_argument(
        "--platform",
        dest="platforms",
        action="append",
        default=None,
        help="platform name or id; repeatable (default linkedin)",
    )
    render.add_argument(
        "--card",
        dest="cards",
        action="append",
        default=None,
        help="card id; repeatable (default all)",
    )
    render.add_argument(
        "--force", action="store_true", help="ignore the content-hash cache"
    )

    video = sub.add_parser(
        "video", help="render a composed run's platform videos to MP4"
    )
    video.add_argument("--run", required=True, help="run id")
    video.add_argument(
        "--platform",
        dest="platforms",
        action="append",
        default=None,
        help="platform name or id; repeatable (default linkedin)",
    )
    video.add_argument(
        "--force", action="store_true", help="ignore the content-hash cache"
    )
    video.add_argument(
        "--workers",
        type=int,
        default=2,
        help="parallel frame-capture workers (default 2)",
    )

    copy = sub.add_parser(
        "copy", help="write validated post.md decks for a run's platforms"
    )
    copy.add_argument("--run", required=True, help="run id")
    copy.add_argument(
        "--platform",
        dest="platforms",
        action="append",
        default=None,
        help="platform name or id; repeatable (default linkedin, x, instagram, whatsapp)",
    )
    copy.add_argument(
        "--no-llm",
        dest="use_llm",
        action="store_false",
        help="use only the deterministic builder",
    )

    qa = sub.add_parser("qa", help="run the quality gates and write qa.json")
    qa.add_argument("--run", required=True, help="run id")
    qa.add_argument(
        "--platform",
        dest="platforms",
        action="append",
        default=None,
        help="platform name or id; repeatable (default every composed platform)",
    )
    qa.add_argument(
        "--card",
        dest="cards",
        action="append",
        default=None,
        help="card id; repeatable (default all)",
    )
    qa.add_argument(
        "--no-ocr",
        dest="use_ocr",
        action="store_false",
        help="skip the OCR cross-check",
    )

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.url, args.out, args.max_pages)
    if args.command == "extract":
        return _extract(args.url, args.out, args.max_pages)
    if args.command == "expire-documents":
        return _expire_documents(args.days, args.tenant)
    if args.command == "render":
        return _render(
            args.run,
            args.platforms or ["linkedin"],
            args.cards or ["hero", "capabilities", "projects", "proof"],
            args.force,
        )
    if args.command == "video":
        return _video(
            args.run,
            args.platforms or ["linkedin"],
            args.force,
            args.workers,
        )
    if args.command == "copy":
        return _copy(
            args.run,
            args.platforms or ["linkedin", "x", "instagram", "whatsapp"],
            args.use_llm,
        )
    if args.command == "qa":
        return _qa(args.run, args.platforms, args.cards, args.use_ocr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
