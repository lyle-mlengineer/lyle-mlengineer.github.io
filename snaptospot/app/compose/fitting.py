"""Measure text in the browser, then fit it without crossing the floor.

The renderer and the composer must agree about line breaks, so measurement runs
in Chromium, not in Python. When a browser is unavailable the composer falls
back to a conservative character estimate and says so in the response.
"""

import logging
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

MIN_RATIO = 0.60
MAX_HEADLINE_LINES = 3
_MAX_ATTEMPTS = 7

_MEASURE_JS = """
() => {
  const card = document.querySelector('.sts-card');
  if (!card) return {card: null, slots: {}};
  const cardRect = card.getBoundingClientRect();
  const slots = {};
  const range = document.createRange();
  for (const el of document.querySelectorAll('[data-slot]')) {
    const rect = el.getBoundingClientRect();
    let lines = 0;
    let lastLineWords = 0;
    if (el.textContent && el.textContent.trim()) {
      range.selectNodeContents(el);
      const rects = Array.from(range.getClientRects()).filter(r => r.width > 0.5 && r.height > 0.5);
      const tops = [];
      for (const r of rects) {
        const top = Math.round(r.top);
        if (!tops.includes(top)) tops.push(top);
      }
      lines = tops.length;
      const lastTop = tops.length ? tops[tops.length - 1] : null;
      let lastText = '';
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const text = node.nodeValue || '';
        for (let i = 0; i < text.length; i += 1) {
          range.setStart(node, i);
          range.setEnd(node, i + 1);
          const charRect = range.getClientRects()[0];
          if (charRect && Math.round(charRect.top) === lastTop) lastText += text[i];
        }
      }
      lastLineWords = lastText.trim().split(/\\s+/).filter(Boolean).length;
    }
    slots[el.getAttribute('data-slot')] = {
      x: rect.left - cardRect.left,
      y: rect.top - cardRect.top,
      w: rect.width,
      h: rect.height,
      lines,
      last_line_words: lastLineWords,
      overflow: el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1,
    };
  }
  return {
    card: {
      w: cardRect.width,
      h: cardRect.height,
      overflow: card.scrollWidth > card.clientWidth + 1
        || card.scrollHeight > card.clientHeight + 1,
    },
    slots,
  };
}
"""


@dataclass(frozen=True)
class SlotMeasurement:
    x: float
    y: float
    w: float
    h: float
    lines: int = 0
    last_line_words: int = 0
    overflow: bool = False


@dataclass
class Measurement:
    slots: dict[str, SlotMeasurement] = field(default_factory=dict)
    overflow: bool = False

    def slot(self, name: str) -> SlotMeasurement | None:
        return self.slots.get(name)


class Measurer(Protocol):
    def measure(self, html: str, width: int, height: int) -> Measurement: ...

    def close(self) -> None: ...


class PlaywrightMeasurer:
    """One Chromium instance per composition run, one page per measurement."""

    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._launch()
        self._context = self._browser.new_context(
            viewport={"width": 1200, "height": 1200},
            device_scale_factor=1,
            java_script_enabled=True,
        )
        self._page = self._context.new_page()
        # Page images and fonts must never touch the network during measurement.
        self._page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.url.startswith(("http://", "https://"))
            else route.continue_(),
        )

    def _launch(self) -> object:
        args = ["--disable-gpu", "--hide-scrollbars", "--force-color-profile=srgb"]
        last_error: Exception | None = None
        for channel in (None, "chrome", "msedge"):
            try:
                return (
                    self._pw.chromium.launch(headless=True, args=args)
                    if channel is None
                    else self._pw.chromium.launch(headless=True, args=args, channel=channel)
                )
            except Exception as exc:  # noqa: BLE001 - try the next local browser
                last_error = exc
        raise RuntimeError("No Playwright browser available") from last_error

    def measure(self, html: str, width: int, height: int) -> Measurement:
        self._page.set_viewport_size({"width": width, "height": height})
        self._page.set_content(html, wait_until="domcontentloaded")
        try:
            self._page.evaluate("document.fonts.ready.then(() => true)")
        except Exception:  # noqa: BLE001 - fonts are best effort
            pass
        payload = self._page.evaluate(_MEASURE_JS)
        card = payload.get("card") if isinstance(payload, dict) else None
        raw_slots = payload.get("slots") if isinstance(payload, dict) else {}
        slots: dict[str, SlotMeasurement] = {}
        for name, row in (raw_slots or {}).items():
            if not isinstance(row, dict):
                continue
            slots[str(name)] = SlotMeasurement(
                x=round(float(row.get("x", 0)), 2),
                y=round(float(row.get("y", 0)), 2),
                w=round(float(row.get("w", 0)), 2),
                h=round(float(row.get("h", 0)), 2),
                lines=int(row.get("lines", 0)),
                last_line_words=int(row.get("last_line_words", 0)),
                overflow=bool(row.get("overflow", False)),
            )
        return Measurement(
            slots=slots,
            overflow=bool(card.get("overflow", False)) if isinstance(card, dict) else False,
        )

    def close(self) -> None:
        try:
            self._context.close()
            self._browser.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001 - teardown is best effort
            pass

    def __enter__(self) -> "PlaywrightMeasurer":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class EstimatingMeasurer:
    """Conservative fallback for machines without Chromium.

    It cannot see the real font metrics, so it over-estimates line counts and
    marks the result as estimated. It exists so a run degrades instead of
    failing; production should pin Chromium.
    """

    def __init__(self, padding: int = 64) -> None:
        self.padding = padding

    def measure(self, html: str, width: int, height: int) -> Measurement:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        card = soup.find(class_="sts-card")
        if card is None:
            return Measurement(overflow=True)
        headline = card.find(attrs={"data-slot": "headline"})
        slots: dict[str, SlotMeasurement] = {}
        overflow = False
        if headline is not None:
            style = str(headline.get("style") or "")
            match = re.search(r"--headline-pt:\s*(\d+)px", style)
            font_pt = int(match.group(1)) if match else 78
            text = re.sub(r"\s+", " ", headline.get_text(" ", strip=True))
            usable = max(80.0, width - self.padding * 2)
            chars_per_line = max(8.0, usable / (font_pt * 0.55))
            lines = max(1, math.ceil(len(text) / chars_per_line))
            remainder = len(text) - (lines - 1) * chars_per_line
            last_words = max(
                1,
                math.ceil(max(1.0, remainder) / max(1.0, chars_per_line / 7)),
            )
            line_height = font_pt * 0.96
            headline_overflow = (
                lines > 5
                or len(text) > chars_per_line * 5
            )
            slots["headline"] = SlotMeasurement(
                x=float(self.padding),
                y=float(self.padding + 40),
                w=float(usable),
                h=round(line_height * lines, 2),
                lines=lines,
                last_line_words=last_words,
                overflow=headline_overflow,
            )
            overflow = headline_overflow
        for index, node in enumerate(card.find_all(attrs={"data-slot": True})):
            name = str(node.get("data-slot"))
            if name in slots:
                continue
            slots[name] = SlotMeasurement(
                x=float(self.padding),
                y=float(self.padding + 40 + index * 40),
                w=float(max(1.0, width - self.padding * 2)),
                h=40.0,
            )
        return Measurement(slots=slots, overflow=overflow)

    def close(self) -> None:
        return


@dataclass(frozen=True)
class FitAttempt:
    density: int
    font_pt: int
    fit: bool
    lines: int = 0
    overflow: bool = False


@dataclass
class FitResult:
    density: int
    font_pt: int
    nominal_pt: int
    measurement: Measurement
    state: str
    lines: int = 0
    attempts: list[FitAttempt] = field(default_factory=list)


_TEXT_SLOT_PREFIXES = (
    "headline",
    "subhead",
    "eyebrow",
    "cta",
    "quote",
    "stat",
    "tile",
    "footnote",
)


def _fits(measurement: Measurement, max_lines: int = MAX_HEADLINE_LINES) -> bool:
    if measurement.overflow:
        return False
    headline = measurement.slot("headline")
    if headline is not None:
        if headline.overflow or headline.lines > max_lines:
            return False
        if headline.lines > 1 and headline.last_line_words == 1:
            return False
    # Decorative chrome (a portrait ring, an image frame) may extend past its
    # own slot without the card overflowing; only text slots are authoritative.
    if any(
        slot.overflow
        for name, slot in measurement.slots.items()
        if name.startswith(_TEXT_SLOT_PREFIXES)
    ):
        return False
    return True


def fit_card(
    build: Callable[[int, int], str],
    measure: Measurer,
    *,
    width: int,
    height: int,
    nominal_pt: int,
    densities: tuple[int, ...],
    min_ratio: float = MIN_RATIO,
    max_lines: int = MAX_HEADLINE_LINES,
) -> FitResult:
    """Shrink display type, then drop density, and never cross the floor."""
    floor = max(9, round(nominal_pt * min_ratio))
    attempts: list[FitAttempt] = []
    changed_density = False

    for density in densities:
        def attempt(size: int, density: int = density) -> tuple[bool, Measurement]:
            measurement = measure.measure(build(density, size), width, height)
            fits = _fits(measurement, max_lines=max_lines)
            headline = measurement.slot("headline")
            attempts.append(
                FitAttempt(
                    density=density,
                    font_pt=size,
                    fit=fits,
                    lines=headline.lines if headline else 0,
                    overflow=measurement.overflow,
                )
            )
            return fits, measurement

        fits, measurement = attempt(nominal_pt)
        if fits:
            lines = measurement.slot("headline").lines if measurement.slot("headline") else 0
            return FitResult(
                density=density,
                font_pt=nominal_pt,
                nominal_pt=nominal_pt,
                measurement=measurement,
                state="density_reduced" if changed_density else "ok",
                lines=lines,
                attempts=attempts,
            )

        low, high = floor, nominal_pt - 1
        best: tuple[int, Measurement] | None = None
        for _ in range(_MAX_ATTEMPTS):
            if low > high:
                break
            size = (low + high) // 2
            if size < floor:
                break
            fits, measurement = attempt(size)
            if fits:
                best = (size, measurement)
                low = size + 1
            else:
                high = size - 1

        if best is not None:
            size, measurement = best
            lines = measurement.slot("headline").lines if measurement.slot("headline") else 0
            return FitResult(
                density=density,
                font_pt=size,
                nominal_pt=nominal_pt,
                measurement=measurement,
                state="density_reduced" if changed_density else "reduced",
                lines=lines,
                attempts=attempts,
            )
        changed_density = True

    final_density = densities[-1]
    measurement = measure.measure(build(final_density, floor), width, height)
    headline = measurement.slot("headline")
    return FitResult(
        density=final_density,
        font_pt=floor,
        nominal_pt=nominal_pt,
        measurement=measurement,
        state="overflow",
        lines=headline.lines if headline else 0,
        attempts=attempts,
    )


def make_measurer() -> tuple[Measurer, bool]:
    """Return a browser measurer when possible, otherwise the estimator."""
    try:
        return PlaywrightMeasurer(), True
    except Exception as exc:  # noqa: BLE001 - degrade, never block composition
        logger.warning("Playwright unavailable for composition, estimating: %s", exc)
        return EstimatingMeasurer(), False
