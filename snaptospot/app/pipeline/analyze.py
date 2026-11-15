from pathlib import Path

from app.config import get_settings
from app.models.run import Run
from app.models.site import Site
from app.pipeline.extract import ExtractionResult, extract_content
from app.pipeline.ingest.crawl import CrawlResult, crawl_site
from app.pipeline.ingest.profile import build_profile
from app.pipeline.understand import enrich_understanding
from app.schemas.profile import SiteProfile


def analyze_site(
    site: Site,
    run: Run,
) -> tuple[SiteProfile, CrawlResult, ExtractionResult]:
    """Crawl, extract and understand one site. Blocking by design for now.

    Celery wraps this in step 5; the function stays synchronous so it can also be
    called from the CLI and tests without a worker.
    """
    settings = get_settings()
    artifact_dir = Path(settings.media_root) / site.tenant_id / site.id / run.id
    crawl = crawl_site(
        site.url,
        max_pages=settings.max_pages,
        artifact_dir=artifact_dir,
    )
    profile = build_profile(crawl)
    profile.understanding = enrich_understanding(profile)
    extraction = extract_content(profile)
    return profile, crawl, extraction
