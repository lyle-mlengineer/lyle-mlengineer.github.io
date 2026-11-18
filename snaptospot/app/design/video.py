"""Platform video registry. Every duration, size and filename lives here.

The registry is data, not branches: the renderer asks for a spec by platform
name and never hard-codes a pixel size or a duration. LinkedIn and X expose the
URL in the last line; Instagram and TikTok can only point at the bio; WhatsApp
is a reply-driven personal message.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.design import VideoSpec

_GB = 1024**3
_MB = 1024**2

LINKEDIN_VIDEO = VideoSpec(
    id="linkedin_video_1080",
    platform="linkedin",
    size=(1080, 1080),
    ratio="1:1",
    duration=15,
    filename="launch-video.mp4",
    poster_filename="video-poster.png",
    max_bytes=5 * _GB,
    last_line="url",
)

X_VIDEO = VideoSpec(
    id="x_video_1920",
    platform="x",
    size=(1920, 1080),
    ratio="16:9",
    duration=15,
    filename="launch-video.mp4",
    poster_filename="video-poster.png",
    max_bytes=512 * _MB,
    last_line="url",
)

INSTAGRAM_VIDEO = VideoSpec(
    id="instagram_reel_1080",
    platform="instagram",
    size=(1080, 1920),
    ratio="9:16",
    duration=18,
    filename="reel.mp4",
    poster_filename="reel-poster.png",
    max_bytes=4 * _GB,
    last_line="bio",
    safe={"top": 260, "bottom": 420},
)

TIKTOK_VIDEO = VideoSpec(
    id="tiktok_video_1080",
    platform="tiktok",
    size=(1080, 1920),
    ratio="9:16",
    duration=21,
    filename="launch-video.mp4",
    poster_filename="video-poster.png",
    max_bytes=4 * _GB,
    last_line="follow",
    safe={"top": 130, "bottom": 320, "right": 120},
)

WHATSAPP_VIDEO = VideoSpec(
    id="whatsapp_status_video_1080",
    platform="whatsapp",
    size=(1080, 1920),
    ratio="9:16",
    duration=18,
    filename="status-video.mp4",
    poster_filename="video-poster.png",
    max_bytes=16 * _MB,
    last_line="reply",
    safe={"bottom": 300},
)

VIDEO_SPECS: dict[str, VideoSpec] = {
    spec.id: spec
    for spec in (
        LINKEDIN_VIDEO,
        X_VIDEO,
        INSTAGRAM_VIDEO,
        TIKTOK_VIDEO,
        WHATSAPP_VIDEO,
    )
}

_BY_PLATFORM: dict[str, VideoSpec] = {spec.platform: spec for spec in VIDEO_SPECS.values()}


def video_spec_for(name: str) -> VideoSpec:
    """Return a video spec by id or platform name."""
    if name in VIDEO_SPECS:
        return VIDEO_SPECS[name]
    try:
        return _BY_PLATFORM[name.casefold()]
    except KeyError as exc:
        raise KeyError(f"Unknown video platform {name!r}") from exc


def video_specs_for(names: list[str]) -> list[VideoSpec]:
    seen: set[str] = set()
    specs: list[VideoSpec] = []
    for name in names:
        spec = video_spec_for(name)
        if spec.id not in seen:
            seen.add(spec.id)
            specs.append(spec)
    return specs


@dataclass(frozen=True)
class LastLine:
    kind: str
    label: str
    value: str


def last_line_for(spec: VideoSpec, url: str) -> LastLine:
    """The closing line each platform can actually act on.

    A clickable URL belongs on LinkedIn/X. Instagram and TikTok cannot carry a
    link in the video, so the last line points at the bio. WhatsApp is personal,
    so it asks for a reply instead of pretending a status is a landing page.
    """
    if spec.last_line == "url":
        return LastLine(kind="url", label="The portfolio is live", value=url)
    if spec.last_line == "bio":
        return LastLine(kind="bio", label="The portfolio is live", value="Link in bio")
    if spec.last_line == "reply":
        return LastLine(kind="reply", label="Want the link?", value="Reply YES")
    return LastLine(kind="follow", label="The portfolio is live", value="Follow the build")
