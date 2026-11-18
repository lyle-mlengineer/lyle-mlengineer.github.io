"""The video timeline, the easing library and deterministic frame capture.

The browser does not animate anything itself. ``renderAt(t)`` is a pure function
of the timeline: given a timestamp it sets every scene's opacity, every element's
enter offset and the progress bar. No CSS transition, no ``requestAnimationFrame``,
no ``Date.now()`` and no ``Math.random()`` are involved, so frame N is always the
same JPEG for the same content, design and template.

Capture is parallelised by contiguous frame ranges. Each worker returns a mapping
from frame index to bytes; the caller reassembles by index, never by completion
order.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.render.chrome import ChromeWorker, get_worker

# Scene boundaries as fractions of the usable content span. They match the hand
# built kit closely enough that the story beats land at the same moments.
_SCENE_FRACTIONS = (
    ("A", 0.000, 0.221),
    ("B", 0.221, 0.495),
    ("C", 0.495, 0.765),
    ("D", 0.765, 1.000),
)

FADE_IN = 0.5
FADE_OUT = 0.34
# The next scene starts fading in this long before the previous one finishes
# leaving. Without the overlap every boundary would dip to a near-black frame.
CROSSFADE = 0.34
HOOK_SECONDS = 0.6


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def cubic_out(value: float) -> float:
    """The house easing: fast start, long settle, no overshoot."""
    value = clamp01(value)
    return 1.0 - (1.0 - value) ** 3


def out_back(value: float, *, overshoot: float = 1.28) -> float:
    """A small overshoot for cards and portraits. Mirror of the JS version."""
    value = clamp01(value)
    return 1.0 + (overshoot + 1.0) * (value - 1.0) ** 3 + overshoot * (value - 1.0) ** 2


def segment(t: float, start: float, end: float) -> float:
    """Progress from ``start`` to ``end``, clamped to 0..1."""
    if end <= start:
        return 1.0 if t >= end else 0.0
    return clamp01((t - start) / (end - start))


def scene_opacity(
    t: float,
    start: float,
    fade_in_end: float,
    fade_out_start: float,
    fade_out_end: float,
) -> float:
    incoming = cubic_out(segment(t, start, fade_in_end))
    outgoing = cubic_out(segment(t, fade_out_start, fade_out_end))
    return incoming * (1.0 - outgoing)


def scene_translate(
    t: float,
    start: float,
    fade_in_end: float,
    fade_out_start: float,
    fade_out_end: float,
) -> float:
    incoming = cubic_out(segment(t, start, fade_in_end))
    outgoing = cubic_out(segment(t, fade_out_start, fade_out_end))
    return (1.0 - incoming) * 34.0 - outgoing * 26.0


def element_state(
    t: float,
    scene_start: float,
    at: float,
    duration: float = 0.5,
    distance: float = 20.0,
    easing: Callable[[float], float] = cubic_out,
) -> tuple[float, float]:
    """Opacity and Y translation for one entering element."""
    progress = easing(segment(t, scene_start + at, scene_start + at + duration))
    return progress, (1.0 - progress) * distance


def frame_times(duration: float, fps: int = 30) -> list[float]:
    """One timestamp per frame, derived from the index, never from a clock."""
    if duration <= 0 or fps <= 0:
        return []
    total = round(duration * fps)
    return [index / fps for index in range(total)]


def poster_time(duration: float) -> float:
    """Poster timestamp: late enough that the composition is complete."""
    return max(0.0, duration - 0.8)


def split_ranges(total: int, workers: int) -> list[tuple[int, int]]:
    """Split ``0..total-1`` into contiguous, deterministic ranges.

    Every index appears exactly once. The first ``remainder`` workers get one
    extra frame, which keeps the split stable for a given total and worker count.
    """
    if total <= 0:
        return []
    workers = max(1, min(workers, total))
    if workers == 1:
        return [(0, total)]
    quotient, remainder = divmod(total, workers)
    ranges: list[tuple[int, int]] = []
    start = 0
    for index in range(workers):
        size = quotient + (1 if index < remainder else 0)
        if size:
            ranges.append((start, start + size))
            start += size
    return ranges


def timeline_payload(duration: float, *, fps: int = 30, hook: bool = False) -> dict[str, object]:
    """Build the JSON the browser's ``renderAt`` function reads.

    TikTok gets a short hook beat before scene A; every other platform starts on
    the hook line itself. Adjacent scenes cross-fade: scene ``i + 1`` begins
    ``CROSSFADE`` seconds before scene ``i`` has finished leaving, so no frame at
    a boundary is left almost empty. The payload is data so the timeline can be
    asserted in Python without a browser.
    """
    lead_in = HOOK_SECONDS if hook else 0.0
    span = max(1.0, duration - lead_in)
    marks = [lead_in + begin * span for _, begin, _ in _SCENE_FRACTIONS]
    marks.append(lead_in + span)
    scenes: list[dict[str, object]] = []
    if hook:
        scenes.append(
            {
                "key": "Hook",
                "start": 0.0,
                "in": 0.0,
                "outStart": round(max(0.0, lead_in - FADE_OUT), 4),
                "out": round(lead_in, 4),
            }
        )
    for index, (key, _begin, _end) in enumerate(_SCENE_FRACTIONS):
        finish = marks[index + 1]
        overlap = CROSSFADE if index > 0 or hook else 0.0
        start = max(0.0, marks[index] - overlap)
        last = key == "D"
        scenes.append(
            {
                "key": key,
                "start": round(start, 4),
                "in": round(start + FADE_IN, 4),
                "outStart": round(finish - FADE_OUT, 4) if not last else 1_000_000.0,
                "out": round(finish, 4) if not last else 1_000_001.0,
            }
        )
    return {"duration": duration, "fps": fps, "leadIn": lead_in, "scenes": scenes}


_RENDER_AT_JS = r"""
(function () {
  var T = __TIMELINE__;
  function clamp(x) { return Math.max(0, Math.min(1, x)); }
  function seg(t, a, b) { return b <= a ? (t >= b ? 1 : 0) : clamp((t - a) / (b - a)); }
  function cubicOut(x) { x = clamp(x); return 1 - Math.pow(1 - x, 3); }
  function outBack(x) {
    x = clamp(x); var c = 1.28;
    return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2);
  }
  var EASE = { cubic_out: cubicOut, out_back: outBack };

  function applyScene(scene, t) {
    var el = document.getElementById("scene" + scene.key);
    if (!el) { return; }
    var fi = cubicOut(seg(t, scene.start, scene.in));
    var fo = cubicOut(seg(t, scene.outStart, scene.out));
    var opacity = fi * (1 - fo);
    el.style.opacity = opacity.toFixed(4);
    el.style.visibility = opacity <= 0.001 ? "hidden" : "visible";
    el.style.transform = "translateY(" + ((1 - fi) * 34 - fo * 26).toFixed(2) + "px)";

    var children = el.querySelectorAll("[data-enter]");
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      var at = parseFloat(child.getAttribute("data-enter") || "0");
      var dur = parseFloat(child.getAttribute("data-enter-dur") || "0.5");
      var dist = parseFloat(child.getAttribute("data-enter-y") || "20");
      var kind = child.getAttribute("data-enter-ease") || "cubic_out";
      var fn = EASE[kind] || cubicOut;
      var k = fn(seg(t - scene.start, at, at + dur));
      child.style.opacity = k.toFixed(3);
      var offset = ((1 - k) * dist).toFixed(2);
      var scaleStart = child.getAttribute("data-enter-scale");
      if (scaleStart !== null) {
        var startScale = parseFloat(scaleStart);
        var scale = startScale + (1 - startScale) * k;
        child.style.transform = "translateY(" + offset + "px) scale(" + scale.toFixed(4) + ")";
      } else {
        child.style.transform = "translateY(" + offset + "px)";
      }
    }

    var containers = el.querySelectorAll("[data-bars]");
    for (var c = 0; c < containers.length; c++) {
      var bars = containers[c].querySelectorAll("i");
      var seed = parseFloat(containers[c].getAttribute("data-seed") || "0");
      for (var b = 0; b < bars.length; b++) {
        var env = 0.42 + 0.58 * Math.sin((b / bars.length) * Math.PI);
        var live = 0.62 + 0.38 * Math.sin(t * 7.5 + b * 0.55 + seed) * Math.sin(t * 2.1 + b * 0.17);
        var h = Math.max(6, 22 + env * 118 * (0.55 + 0.55 * live));
        bars[b].style.height = h.toFixed(1) + "px";
        bars[b].style.opacity = (0.35 + 0.65 * Math.min(1, fi)).toFixed(2);
      }
    }
  }

  window.renderAt = function (t) {
    t = Math.max(0, Math.min(T.duration, Number(t) || 0));
    for (var i = 0; i < T.scenes.length; i++) { applyScene(T.scenes[i], t); }
    var bar = document.getElementById("progress");
    if (bar) { bar.style.width = (clamp(t / T.duration) * 100).toFixed(2) + "%"; }
  };
  window.renderAt(0);
})();
"""


def render_at_script(
    payload: dict[str, object] | None = None,
    *,
    duration: float = 15,
    fps: int = 30,
    hook: bool = False,
) -> str:
    """Return the self-contained ``window.renderAt`` script for a timeline."""
    data = payload if payload is not None else timeline_payload(duration, fps=fps, hook=hook)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return _RENDER_AT_JS.replace("__TIMELINE__", encoded)


# A worker only needs the history of the scene it is about to capture. The
# longest entrance is a caption that starts 1.5 s after its scene and runs for
# 0.5 s, so replaying this much of the timeline is enough to make the raster
# cache match a single-worker run.
WARMUP_SECONDS = 2.5


def _capture_range(
    html: str,
    width: int,
    height: int,
    times: list[float],
    start: int,
    end: int,
    worker_factory: Callable[[], ChromeWorker],
    image_format: str,
    quality: int,
) -> dict[int, bytes]:
    worker = worker_factory()
    # Chromium's text raster cache is history-dependent: an element first
    # revealed mid-transform rasterises differently from one that was already
    # painted. A worker that starts at frame N would therefore produce different
    # pixels than a single worker that reached N by playing the timeline. Replay
    # the window before the range (and discard it) so every range has the same
    # visible history, then keep only the assigned range.
    warm_from = times[start] - WARMUP_SECONDS if start else 0.0
    first = 0
    while first < start and times[first] < warm_from:
        first += 1
    samples = [(index, times[index]) for index in range(first, end)]
    captured = worker.capture_frames(
        html,
        width,
        height,
        samples,
        image_format=image_format,
        quality=quality,
    )
    return {index: data for index, data in captured.items() if index >= start}


def capture_frames_parallel(
    html: str,
    width: int,
    height: int,
    times: list[float],
    *,
    workers: int = 1,
    image_format: str = "jpeg",
    quality: int = 95,
    worker_factory: Callable[[], ChromeWorker] | None = None,
) -> dict[int, bytes]:
    """Capture every timestamp, splitting the work into contiguous ranges.

    The result is keyed by frame index and sorted, so a faster worker cannot
    reorder the frames that reach ffmpeg.
    """
    factory = worker_factory or get_worker
    ranges = split_ranges(len(times), workers)
    if not ranges:
        return {}
    if len(ranges) == 1:
        start, end = ranges[0]
        return dict(
            sorted(
                _capture_range(
                    html, width, height, times, start, end, factory, image_format, quality
                ).items()
            )
        )

    results: dict[int, bytes] = {}
    with ThreadPoolExecutor(max_workers=len(ranges), thread_name_prefix="snap-video") as pool:
        futures = [
            pool.submit(
                _capture_range,
                html,
                width,
                height,
                times,
                start,
                end,
                factory,
                image_format,
                quality,
            )
            for start, end in ranges
        ]
        for future in futures:
            results.update(future.result())
    return dict(sorted(results.items()))


def write_frames(frames: dict[int, bytes], directory: object) -> list[object]:
    """Write ``f_0000.jpg`` files in index order; returns the written paths."""
    from pathlib import Path

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[object] = []
    for index in sorted(frames):
        path = root / f"f_{index:04d}.jpg"
        path.write_bytes(frames[index])
        paths.append(path)
    return paths


def mean_duration(times: list[float]) -> float:
    """Small helper used by tests and diagnostics."""
    return sum(times) / len(times) if times else 0.0


def waveform_heights(count: int, t: float, *, seed: float = 0.0) -> list[float]:
    """Python mirror of the browser's deterministic waveform for tests."""
    heights: list[float] = []
    for index in range(count):
        envelope = 0.42 + 0.58 * math.sin((index / count) * math.pi)
        live = (
            0.62
            + 0.38
            * math.sin(t * 7.5 + index * 0.55 + seed)
            * math.sin(t * 2.1 + index * 0.17)
        )
        heights.append(max(6.0, 22.0 + envelope * 118.0 * (0.55 + 0.55 * live)))
    return heights
