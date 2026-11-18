"""Poster frames at ``duration - 0.8 s``.

The first frame of an animated kit is nearly empty and makes a bad thumbnail, so
the poster is captured after the composition has settled. A poster that is a
flat colour is rejected rather than shipped.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageStat

from app.render.chrome import ChromeWorker, get_worker, normalise_png
from app.render.frames import poster_time
from app.schemas.design import VideoSpec


@dataclass(frozen=True)
class Poster:
    data: bytes
    timestamp: float
    width: int
    height: int
    blank: bool


def frame_stats(data: bytes) -> dict[str, float]:
    """Enough image statistics to recognise a flat or near-flat frame."""
    with Image.open(io.BytesIO(data)) as source:
        grey = source.convert("L")
        stat = ImageStat.Stat(grey)
        histogram = grey.histogram()
    total = sum(histogram) or 1
    dominant = max(histogram) / total
    unique = sum(1 for count in histogram if count)
    return {
        "stddev": float(stat.stddev[0]),
        "dominant": dominant,
        "unique": float(unique),
        "mean": float(stat.mean[0]),
    }


def is_blank(data: bytes, *, stddev: float = 3.0, dominant: float = 0.985) -> bool:
    """A poster is blank when one grey level owns almost the whole frame."""
    stats = frame_stats(data)
    return stats["stddev"] < stddev or stats["dominant"] > dominant or stats["unique"] < 4


def capture_poster(
    html: str,
    spec: VideoSpec,
    *,
    worker: ChromeWorker | None = None,
    timestamp: float | None = None,
) -> Poster:
    renderer = worker or get_worker()
    moment = poster_time(spec.duration) if timestamp is None else timestamp
    raw = renderer.capture_frame(
        html,
        spec.size[0],
        spec.size[1],
        moment,
        image_format="png",
    )
    data = normalise_png(raw)
    return Poster(
        data=data,
        timestamp=moment,
        width=spec.size[0],
        height=spec.size[1],
        blank=is_blank(data),
    )


def poster_time_for(spec: VideoSpec) -> float:
    return poster_time(spec.duration)
