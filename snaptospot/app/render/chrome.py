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
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger(__name__)

DEVICE_SCALE_FACTOR = 2
RENDERER_VERSION = "chrome-playwright@1"
VIDEO_RENDERER_VERSION = "chrome-playwright@1+ffmpeg"

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


def normalise_png(raw: bytes) -> bytes:
    """Re-encode a 1x screenshot without a timestamp or software chunk."""
    with Image.open(io.BytesIO(raw)) as source:
        image = source.convert("RGB")
        buffer = io.BytesIO()
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

    def capture_frames(
        self,
        html: str,
        width: int,
        height: int,
        samples: Sequence[tuple[int, float]],
        *,
        image_format: str = "jpeg",
        quality: int = 95,
    ) -> dict[int, bytes]:
        """Capture one 1x frame per ``(index, timestamp)`` sample.

        The page is loaded once and ``window.renderAt(t)`` is called for every
        timestamp. JPEG is the shipping frame format: it is several times faster
        than PNG and H.264 removes any visible difference.
        """
        if self.closed:
            raise ChromeRenderError("Renderer is closed")
        if not samples:
            return {}
        if image_format not in {"jpeg", "png"}:
            raise ChromeRenderError(f"Unsupported frame format {image_format!r}")

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
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            page.set_content(html, wait_until="domcontentloaded")
            page.evaluate(_READY_JS)
            page.evaluate(
                "() => {"
                "  if (typeof window.renderAt !== 'function') {"
                "    throw new Error('video template did not define renderAt');"
                "  }"
                "}"
            )
            captured: dict[int, bytes] = {}
            for index, timestamp in samples:
                page.evaluate("(t) => window.renderAt(t)", float(timestamp))
                params: dict[str, object] = {
                    "format": image_format,
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                }
                if image_format == "jpeg":
                    params["quality"] = quality
                payload = session.send("Page.captureScreenshot", params)
                captured[index] = base64.b64decode(payload["data"])
            return captured
        except ChromeRenderError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface one clear error
            raise ChromeRenderError(f"Frame capture failed: {exc}") from exc
        finally:
            try:
                page.close()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass

    def capture_frame(
        self,
        html: str,
        width: int,
        height: int,
        timestamp: float,
        *,
        image_format: str = "png",
        quality: int = 95,
    ) -> bytes:
        """Capture a single 1x frame; PNG results are metadata-free."""
        frames = self.capture_frames(
            html,
            width,
            height,
            [(0, timestamp)],
            image_format=image_format,
            quality=quality,
        )
        data = frames[0]
        return normalise_png(data) if image_format == "png" else data

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
