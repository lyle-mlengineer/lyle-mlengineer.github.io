import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx

from app.config import get_settings
from app.pipeline.ingest.errors import CrawlError
from app.pipeline.ingest.security import assert_url_allowed

logger = logging.getLogger(__name__)


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status_code: int
    html: str
    screenshot_path: str | None = None
    # Maps the data-sts-box index on a rendered node to [x, y, width, height].
    bboxes: dict[str, list[float]] | None = None


class Fetcher(Protocol):
    def fetch(self, url: str, screenshot_path: str | None = None) -> FetchedPage: ...

    def fetch_text(self, url: str) -> tuple[int, str]: ...

    def close(self) -> None: ...


class HttpxFetcher:
    """Static HTML fetcher. Fast, no JavaScript, used as the fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = httpx.Client(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.fetch_timeout_seconds,
        )

    def _get(self, url: str) -> tuple[str, httpx.Response]:
        current = url
        for _ in range(6):
            assert_url_allowed(current)
            response = self.client.get(current, follow_redirects=False)
            location = response.headers.get("location")
            if response.is_redirect and location:
                current = urljoin(current, location)
                continue
            return current, response
        raise CrawlError("Too many redirects")

    def fetch(self, url: str, screenshot_path: str | None = None) -> FetchedPage:
        final_url, response = self._get(url)
        response.raise_for_status()
        return FetchedPage(
            url=url,
            final_url=final_url,
            status_code=response.status_code,
            html=response.text,
            screenshot_path=None,
        )

    def fetch_text(self, url: str) -> tuple[int, str]:
        _, response = self._get(url)
        return response.status_code, response.text

    def close(self) -> None:
        self.client.close()


_TAG_BLOCKS_JS = """
() => {
  const selector = 'h1,h2,h3,h4,p,li,blockquote,figcaption,td,th,dt,dd';
  const nodes = Array.from(document.querySelectorAll(selector));
  const out = [];
  nodes.forEach((el, index) => {
    const rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    el.setAttribute('data-sts-box', String(index));
    out.push([index, rect.x + window.scrollX, rect.y + window.scrollY, rect.width, rect.height]);
  });
  return out;
}
"""


def _tag_block_boxes(page: object) -> dict[str, list[float]]:
    """Tag block-level nodes in the live DOM with their viewport boxes."""
    try:
        raw = page.evaluate(_TAG_BLOCKS_JS)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - boxes are an enhancement, not a requirement
        return {}
    boxes: dict[str, list[float]] = {}
    for row in raw or []:
        if len(row) != 5:
            continue
        index, x, y, width, height = row
        boxes[str(index)] = [
            round(float(x), 1),
            round(float(y), 1),
            round(float(width), 1),
            round(float(height), 1),
        ]
    return boxes


class PlaywrightFetcher:
    """Rendered fetcher. Runs JavaScript and captures screenshots."""

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        settings = get_settings()
        self._pw = sync_playwright().start()
        self._browser = self._launch()
        self._context = self._browser.new_context(
            user_agent=settings.user_agent,
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            java_script_enabled=True,
        )
        self._timeout_ms = settings.fetch_timeout_seconds * 1000
        self._text_client = HttpxFetcher()

    def _launch(self) -> Any:
        """Prefer bundled Chromium, then an installed Chrome or Edge.

        The download can be blocked on restrictive networks. Falling back to a
        system browser keeps rendering available locally; production images pin
        bundled Chromium for reproducibility.
        """
        args = ["--disable-gpu", "--hide-scrollbars"]
        last_error: Exception | None = None
        for channel in (None, "chrome", "msedge"):
            try:
                browser = (
                    self._pw.chromium.launch(headless=True, args=args)
                    if channel is None
                    else self._pw.chromium.launch(headless=True, args=args, channel=channel)
                )
                logger.info("Playwright using %s", channel or "bundled Chromium")
                return browser
            except Exception as exc:  # noqa: BLE001 - try the next local browser
                last_error = exc
        raise RuntimeError("No Playwright browser available") from last_error

    def fetch(self, url: str, screenshot_path: str | None = None) -> FetchedPage:
        assert_url_allowed(url)
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until="load", timeout=self._timeout_ms)
            assert_url_allowed(page.url)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:  # noqa: BLE001 - network idle is best effort
                pass
            page.evaluate("document.fonts.ready.then(() => true)")
            bboxes = _tag_block_boxes(page)
            html = page.content()
            if screenshot_path:
                Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=screenshot_path, full_page=True)
            return FetchedPage(
                url=url,
                final_url=page.url,
                status_code=response.status if response else 200,
                html=html,
                screenshot_path=screenshot_path,
                bboxes=bboxes,
            )
        finally:
            page.close()

    def fetch_text(self, url: str) -> tuple[int, str]:
        return self._text_client.fetch_text(url)

    def close(self) -> None:
        self._text_client.close()
        self._context.close()
        self._browser.close()
        self._pw.stop()


def make_fetcher() -> Fetcher:
    settings = get_settings()
    if settings.use_playwright:
        try:
            return PlaywrightFetcher()
        except Exception as exc:  # noqa: BLE001 - any launch failure falls back
            logger.warning("Playwright unavailable, falling back to static fetch: %s", exc)
    return HttpxFetcher()
