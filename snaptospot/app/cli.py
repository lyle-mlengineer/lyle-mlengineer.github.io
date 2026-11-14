import argparse
import hashlib
import json
import sys
from pathlib import Path

from app.config import get_settings
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snaptospot", description="SnapToSpot tools")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="crawl a site and print its SiteProfile")
    ingest.add_argument("url")
    ingest.add_argument("--out", help="write the profile to a JSON file")
    ingest.add_argument("--max-pages", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _ingest(args.url, args.out, args.max_pages)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
