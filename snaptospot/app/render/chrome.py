"""A persistent Chromium worker that turns HTML into deterministic PNG bytes.

One browser and one context live for the lifetime of a worker (a Celery worker
process or a FastAPI thread-pool thread). Each asset gets a fresh tab so a page
cannot leak state into the next capture. Screenshots are taken at 2x and reduced
with Lanczos to 1x, which keeps display type crisp without changing the page's
own layout dimensions.
"""

from __future__ import annotations

import base64
import io
import logging
import threading
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger(__name__)

DEVICE_SCALE_FACTOR = 2
RENDERER_VERSION = "chrome-playwright@1"

# Flags that remove sources of non-determinism: GPU rasterisation, colour
# management drift, scrollbars, LCD subpixel text and background networking.
_LAUNCH_ARGS = [
    "--disable-gpu",
    "--hide-scrollbars",
    "--force-color-profile=srgb",
    "--force-device-scale-factor=1",
    "--disable-lcd-text",
    "--font-render-hinting=none",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-extensions",
    "--mute-audio",
    "--metrics-recording-only",
]

_READY_JS = """
async () => {
  if (document.readyState !== 'complete') {
    await new Promise(resolve => {
      window.addEventListener('load', resolve, { once: true });
    });
  }
  await Promise.all(Array.from(document.images).map(img => {
    if (img.complete) return true;
    return new Promise(resolve => {
      img.addEventListener('load', resolve, { once: true });
      img.addEventListener('error', resolve, { once: true });
    });
  }));
  if (document.fonts && document.fonts.ready) {
    await document.fonts.ready;
  }
  return {
    readyState: document.readyState,
    images: document.images.length,
    fonts: document.fonts ? document.fonts.status : 'unknown',
  };
}
"""


class ChromeRenderError(RuntimeError):
    """Chromium was unavailable or a capture failed."""


@dataclass(frozen=True)
class Capture:
    data: bytes
    width: int
    height: int
    scale: int = DEVICE_SCALE_FACTOR


def _downsample(raw: bytes, width: int, height: int) -> bytes:
    """Reduce a 2x capture to the exact target size and strip metadata."""
    with Image.open(io.BytesIO(raw)) as source:
        image = source.convert("RGB")
        expected = (width * DEVICE_SCALE_FACTOR, height * DEVICE_SCALE_FACTOR)
        if image.size != expected:
            # A viewport override can be rounded by the browser. Resampling the
            # full surface first keeps the ratio correct before the final pass.
            image = image.resize(expected, Image.Resampling.LANCZOS)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        # Pillow writes no text chunks unless pnginfo is passed, so the result
        # carries no timestamp, software tag or EXIF block.
        image.save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


class ChromeWorker:
    """One Chromium instance, one context, one page per capture."""

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._launch()
        self._context = self._browser.new_context(
            viewport={"width": 1200, "height": 1200},
            device_scale_factor=DEVICE_SCALE_FACTOR,
            java_script_enabled=True,
            locale="en-US",
            timezone_id="UTC",
            reduced_motion="reduce",
            forced_colors="none",
        )
        # Nothing may come from the network during a capture. Images are
        # inlined as data URIs and fonts are pinned local families.
        self._context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.url.startswith(("http://", "https://"))
                else route.continue_()
            ),
        )
        self.closed = False
        self.channel = getattr(self._browser, "channel", None)

    def _launch(self) -> object:
        last_error: Exception | None = None
        for channel in (None, "chrome", "msedge"):
            try:
                return (
                    self._playwright.chromium.launch(headless=True, args=_LAUNCH_ARGS)
                    if channel is None
                    else self._playwright.chromium.launch(
                        headless=True, args=_LAUNCH_ARGS, channel=channel
                    )
                )
            except Exception as exc:  # noqa: BLE001 - try the next local browser
                last_error = exc
        raise ChromeRenderError("No Playwright browser available") from last_error

    @property
    def version(self) -> str:
        try:
            return str(self._browser.version)
        except Exception:  # noqa: BLE001 - version is metadata, not a gate
            return "unknown"

    def capture(self, html: str, width: int, height: int) -> Capture:
        if self.closed:
            raise ChromeRenderError("Renderer is closed")
        page = self._context.new_page()
        try:
            session = self._context.new_cdp_session(page)
            session.send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": height,
                    "screenWidth": width,
                    "screenHeight": height,
                    "deviceScaleFactor": DEVICE_SCALE_FACTOR,
                    "mobile": False,
                },
            )
            page.set_content(html, wait_until="domcontentloaded")
            page.evaluate(_READY_JS)
            payload = session.send(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                },
            )
            raw = base64.b64decode(payload["data"])
            return Capture(
                data=_downsample(raw, width, height),
                width=width,
                height=height,
            )
        except Exception as exc:  # noqa: BLE001 - surface one clear error
            raise ChromeRenderError(f"Capture failed: {exc}") from exc
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._context.close()
            self._browser.close()
            self._playwright.stop()
        except Exception:  # noqa: BLE001 - teardown is best effort
            pass

    def __enter__(self) -> ChromeWorker:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


_local = threading.local()


def get_worker() -> ChromeWorker:
    """Return this thread's persistent Chromium worker."""
    worker = getattr(_local, "worker", None)
    if not isinstance(worker, ChromeWorker) or worker.closed:
        worker = ChromeWorker()
        _local.worker = worker
    return worker


def close_worker() -> None:
    worker = getattr(_local, "worker", None)
    if isinstance(worker, ChromeWorker):
        worker.close()
    _local.worker = None


def render_html(html: str, width: int, height: int) -> bytes:
    """Capture one HTML document at 2x and return a 1x PNG."""
    return get_worker().capture(html, width, height).data
