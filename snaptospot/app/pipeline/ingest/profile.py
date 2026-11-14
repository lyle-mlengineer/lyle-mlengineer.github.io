import hashlib

from bs4 import BeautifulSoup

from app.models.base import utcnow
from app.pipeline.ingest.assets import (
    harvest_fonts,
    harvest_images,
    harvest_palette,
    pick_logo,
)
from app.pipeline.ingest.blocks import extract_page, page_title
from app.pipeline.ingest.crawl import CrawlResult
from app.pipeline.ingest.entities import extract_entities
from app.schemas.profile import Brand, ImageAsset, Observed, Page, SiteProfile


def _merge_images(existing: dict[str, ImageAsset], found: list[ImageAsset]) -> None:
    for image in found:
        existing.setdefault(image.url, image)


def build_profile(crawl: CrawlResult) -> SiteProfile:
    """Assemble the deterministic half of a ``SiteProfile``.

    The profile contains only what was observed on the crawled pages. Gaps and
    inferred meaning are added later; this function never fills a missing value
    with a guess.
    """
    images: dict[str, ImageAsset] = {}
    pages: list[Page] = []
    home_html = crawl.pages[0].fetched.html if crawl.pages else ""
    home_url = crawl.pages[0].fetched.final_url if crawl.pages else crawl.url

    for item in crawl.pages:
        page = extract_page(
            item.fetched.html,
            item.fetched.final_url,
            item.page_id,
            item.fetched.bboxes,
        )
        pages.append(page)
        soup = BeautifulSoup(item.fetched.html, "lxml")
        _merge_images(images, harvest_images(soup, item.fetched.final_url))

    home_soup = BeautifulSoup(home_html, "lxml")
    visible_text = "\n".join(
        block.text for page in pages for block in page.blocks
    )
    entities = extract_entities(home_soup, home_url, visible_text)

    screenshot = crawl.pages[0].fetched.screenshot_path if crawl.pages else None
    colors = harvest_palette(screenshot, home_html)
    fonts = harvest_fonts(home_soup, home_html)
    image_list = list(images.values())
    logo = pick_logo(image_list, home_soup, home_url)

    digest = hashlib.sha256()
    for item in crawl.pages:
        digest.update(item.fetched.final_url.encode())
        digest.update(item.fetched.html.encode(errors="ignore"))
    site_hash = f"sha256:{digest.hexdigest()}"

    title = crawl.title or (page_title(home_soup) if home_html else home_url)

    return SiteProfile(
        url=crawl.url,
        title=title.strip(),
        pages=pages,
        brand=Brand(colors=colors, fonts=fonts, logo=logo),
        entities=entities,
        images=image_list,
        observed=Observed(
            page_count=len(pages),
            asset_count=len(image_list),
            crawled_at=utcnow(),
            site_hash=site_hash,
        ),
        gaps=[],
    )
