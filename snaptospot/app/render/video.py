"""Render deterministic MP4s and poster frames for a composed run.

Video deliberately does not depend on the composed still layouts. It builds its
own four-scene narrative from the same ``ContentModel`` and ``build_slots``
contract, so a copy edit cannot leave the stills and the video telling different
stories.

The cache key is the same four-tuple the still renderer uses, written into a
separate ``video-cache`` namespace: content model, design system, platform and
template version.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.compose.ast import build_slots
from app.compose.templates import render_video, standalone
from app.config import get_settings
from app.design.platforms import ratio_class, spec_for
from app.design.tokens import design_system_hash
from app.design.video import last_line_for, video_specs_for
from app.models import AuditLog, Run
from app.render.assets import AssetStore, prepare_document
from app.render.chrome import VIDEO_RENDERER_VERSION, ChromeWorker, get_worker
from app.render.encode import EncodedVideo, encode_frames, probe_video
from app.render.frames import (
    capture_frames_parallel,
    frame_times,
    poster_time,
    render_at_script,
    write_frames,
)
from app.render.poster import capture_poster
from app.render.service import ComposeFirstError, _design, _relative
from app.render.stills import content_model_hash, render_key
from app.schemas.content import ContentModel
from app.schemas.design import DesignSystem, VideoSpec
from app.schemas.profile import SiteProfile
from app.schemas.video import (
    RenderedVideoOut,
    VideoIn,
    VideoOut,
    VideoProbeOut,
)

logger = logging.getLogger(__name__)


class VideoError(ValueError):
    """The run cannot be rendered to video, or the platform is unknown."""


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def _model(run: Run) -> ContentModel:
    if not run.content_model_json:
        raise ComposeFirstError("run has no content model; analyze the site first")
    try:
        return ContentModel.model_validate(run.content_model_json)
    except ValueError as exc:
        raise VideoError("run content model is invalid; re-analyze the site") from exc


def _profile(run: Run) -> SiteProfile:
    if not run.profile_json:
        raise ComposeFirstError("run has no site profile; analyze the site first")
    try:
        return SiteProfile.model_validate(run.profile_json)
    except ValueError as exc:
        raise VideoError("run profile is invalid; re-analyze the site") from exc


def _join(values: list[str], separator: str = " · ") -> str:
    return separator.join(value.strip() for value in values if value and value.strip())


def _headline(parts: list[object], fallback: str) -> list[dict[str, str]]:
    if parts:
        return [
            {
                "text": str(getattr(part, "text", "")),
                "emphasis": str(getattr(part, "emphasis", "none")),
            }
            for part in parts
        ]
    return [{"text": fallback, "emphasis": "last_word"}]


def _still_spec(spec: VideoSpec):
    try:
        return spec_for(spec.platform)
    except KeyError:
        return spec_for("linkedin")


def _sentence(text: str) -> str:
    """First sentence, with the trailing punctuation kept."""
    for index, char in enumerate(text):
        if char in ".!?" and index + 1 < len(text) and text[index + 1] == " ":
            return text[: index + 1].strip()
    return text.strip()


def _short_hook(text: str, limit: int = 52) -> tuple[str, str]:
    """Split a thesis into a display hook and the supporting detail.

    The still hero can afford a full thesis; a 122 px video headline cannot. The
    hook keeps the clause before a colon (or the first sentence), then trims at a
    word boundary if it is still too long. The remainder becomes the subhead, so
    no copy is lost.
    """
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return "", ""
    head, separator, tail = cleaned.partition(":")
    if not separator:
        head, tail = cleaned, ""
    head = head.strip()
    if len(head) > limit:
        head = _sentence(head)
    if len(head) > limit:
        words = head.split()
        kept: list[str] = []
        for word in words:
            candidate = " ".join([*kept, word])
            if len(candidate) > limit and kept:
                break
            kept.append(word)
        head = " ".join(kept) or head[:limit].rsplit(" ", 1)[0]
        remainder = cleaned[len(head) :].strip(" ,;:-")
        tail = remainder or tail
    tail = tail.strip(" ,;:-")
    if tail:
        tail = tail[0].upper() + tail[1:]
    return head, tail


def _hero_size(text: str, width: int, ratio: str) -> int:
    """Largest display size that keeps a short hook inside three lines.

    This is a character estimate, not a measurement: it is deterministic, runs
    in Python and is deliberately conservative. Display glyphs average roughly
    0.6 em in uppercase, and the scene keeps 3 lines of headroom.
    """
    pad = {("9:16"): 128, ("16:9"): 168}.get(ratio, 144)
    usable = max(320.0, width - pad)
    longest = max((len(word) for word in text.split()), default=1)
    for size in (148, 136, 124, 114, 104, 94, 84, 76):
        per_line = usable / (size * 0.6)
        if longest <= per_line and len(text) <= per_line * 3:
            return size
    return 72


def build_video_context(
    model: ContentModel,
    profile: SiteProfile,
    design: DesignSystem,
    spec: VideoSpec,
    *,
    today: date | None = None,
) -> dict[str, object]:
    """Turn the content model into the four scenes the timeline animates."""
    still = _still_spec(spec)
    hero = build_slots("hero", 1, model, profile, design, still, today=today)
    capabilities = build_slots("capabilities", 4, model, profile, design, still, today=today)
    projects = build_slots("projects", 4, model, profile, design, still, today=today)
    proof = build_slots("proof", 4, model, profile, design, still, today=today)

    person = profile.entities.person
    brand = person.name or profile.entities.org.name or profile.title or "Portfolio"
    role = person.role or profile.entities.org.name or ""
    location = person.location or ""
    tag = _join([role, location]) or profile.title or brand
    cta = model.cta
    project_names = [tile.title for tile in projects.tiles]
    last_line = last_line_for(spec, cta.url)

    hero_headline = _headline(hero.headline, model.thesis)
    hero_text = " ".join(part["text"] for part in hero_headline)
    hook_text, detail = _short_hook(hero_text)
    hook_text = hook_text or brand
    subhead = hero.subhead or detail or model.thesis
    caption = model.audience or model.thesis
    if caption.strip() == subhead.strip():
        caption = model.thesis
    safe = {"top": 0, "bottom": 0, "left": 0, "right": 0, **spec.safe}
    hook = spec.platform == "tiktok"

    scenes: dict[str, dict[str, object]] = {
        "a": {
            "eyebrow": hero.eyebrow or role or "Portfolio",
            "headline": [{"text": hook_text, "emphasis": "last_word"}],
            "subhead": subhead,
            "caption": caption,
            "foot": _join([location, cta.label]) or cta.url,
        },
        "b": {
            "eyebrow": capabilities.eyebrow,
            "headline": _headline(capabilities.headline, model.thesis),
            "subhead": capabilities.subhead,
            "tiles": [tile.model_dump(mode="json") for tile in capabilities.tiles],
            "caption": model.thesis,
            "foot": _join(
                [
                    f"{len(capabilities.tiles)} capabilities" if capabilities.tiles else "",
                    location,
                ]
            )
            or model.thesis,
        },
        "c": {
            "eyebrow": proof.eyebrow,
            "headline": _headline(proof.headline, "Proof, not promises."),
            "subhead": proof.subhead,
            "stats": [stat.model_dump(mode="json") for stat in proof.stats],
            "quote": proof.quote.model_dump(mode="json") if proof.quote else None,
            "projects": project_names,
            "caption": "Every number carries a source.",
            "foot": _join(project_names) or model.thesis,
        },
        "d": {
            "eyebrow": "The portfolio is live",
            "name": brand,
            "role": _join([role, location]) or profile.title or "",
            "portrait": hero.media[0].model_dump(mode="json") if hero.media else None,
            "caption": model.audience or model.thesis,
            "foot": _join([role, location]) or profile.title or brand,
        },
    }

    return {
        "width": spec.size[0],
        "height": spec.size[1],
        "ratio_class": ratio_class(spec.ratio),
        "duration": spec.duration,
        "fps": spec.fps,
        "safe": safe,
        "hero_size": _hero_size(hook_text, spec.size[0], spec.ratio),
        "tokens": design.tokens.model_dump(mode="json"),
        "portrait_treatment": design.portrait_treatment.model_dump(mode="json"),
        "media_treatment": design.media_treatment.model_dump(mode="json"),
        "brand": brand,
        "tag": tag,
        "role": role,
        "location": location,
        "hook": hook,
        "hook_text": hook_text,
        "scenes": scenes,
        "last_line": asdict(last_line),
        "cta": cta.model_dump(mode="json"),
        "template_version": spec.template_version,
        "timeline_script": render_at_script(
            duration=spec.duration,
            fps=spec.fps,
            hook=hook,
        ),
    }


def video_warnings(context: dict[str, object], spec: VideoSpec) -> list[str]:
    scenes = context["scenes"]
    assert isinstance(scenes, dict)
    warnings: list[str] = []
    if not scenes["b"].get("tiles"):
        warnings.append("video capabilities scene has no offerings; showing the thesis instead.")
    if not scenes["c"].get("stats"):
        warnings.append("video proof scene has no tier A/B stats; showing the headline only.")
    if not scenes["d"].get("portrait"):
        warnings.append("no portrait could be loaded; the sign-off scene uses type only.")
    return warnings


def _resolve_portrait(context: dict[str, object], store: AssetStore, base_dir: Path | None) -> None:
    scenes = context["scenes"]
    assert isinstance(scenes, dict)
    scene = scenes["d"]
    assert isinstance(scene, dict)
    portrait = scene.get("portrait")
    if not isinstance(portrait, dict):
        return
    resolved = store.resolve(str(portrait.get("url") or ""), base_dir)
    if resolved is None:
        scene["portrait"] = None
    else:
        scene["portrait"] = {**portrait, "url": resolved}


def video_html(
    context: dict[str, object],
    *,
    store: AssetStore | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Render the template and make the page self-contained for capture."""
    settings = get_settings()
    asset_store = store or AssetStore(
        Path(settings.media_root) / "video-cache" / "assets",
        fetch_remote=bool(settings.render_fetch_remote),
    )
    base = Path(base_dir) if base_dir is not None else None
    _resolve_portrait(context, asset_store, base)
    fragment = render_video(context)
    document = standalone(fragment, int(context["width"]), int(context["height"]))
    return prepare_document(document, base_dir=base, store=asset_store)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class VideoCache:
    """Content-addressed MP4 + poster store rooted at ``media_root/video-cache``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def directory(self, key: str) -> Path:
        return self.root / key[:2] / key

    def read(self, key: str, filename: str) -> bytes | None:
        path = self.directory(key) / filename
        try:
            return path.read_bytes() if path.exists() else None
        except OSError:
            return None

    def write(self, key: str, filename: str, data: bytes) -> Path:
        path = self.directory(key) / filename
        _write_atomic(path, data)
        return path


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _copy_if_changed(source: bytes, destination: Path) -> None:
    if destination.exists():
        try:
            if destination.read_bytes() == source:
                return
        except OSError:
            pass
    _write_atomic(destination, source)


# ---------------------------------------------------------------------------
# One asset
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedVideoFile:
    platform: str
    filename: str
    poster_filename: str
    path: Path
    poster_path: Path
    width: int
    height: int
    duration: float
    fps: int
    size: int
    poster_size: int
    sha256: str
    poster_sha256: str
    cache_key: str
    cached: bool
    template_version: str
    poster_timestamp: float
    within_ceiling: bool
    probe: dict[str, object]
    warnings: tuple[str, ...]


def _poster_with_fallback(
    html: str,
    spec: VideoSpec,
    *,
    worker_factory: Callable[[], ChromeWorker],
) -> tuple[bytes, float, bool]:
    """Prefer the settled poster; fall back to a later beat if it is flat."""
    candidates = [
        poster_time(spec.duration),
        round(spec.duration * 0.72, 4),
        round(spec.duration * 0.55, 4),
    ]
    worker = worker_factory()
    last: tuple[bytes, float, bool] | None = None
    for timestamp in candidates:
        poster = capture_poster(html, spec, worker=worker, timestamp=timestamp)
        last = (poster.data, poster.timestamp, poster.blank)
        if not poster.blank:
            return last
    assert last is not None
    return last


def render_video_asset(
    spec: VideoSpec,
    context: dict[str, object],
    *,
    content_hash: str,
    design_hash: str,
    output_root: Path | str,
    cache_root: Path | str,
    workers: int = 2,
    reuse_cache: bool = True,
    store: AssetStore | None = None,
    base_dir: Path | str | None = None,
    worker_factory: Callable[[], ChromeWorker] | None = None,
) -> RenderedVideoFile:
    """Render one platform video, using the content-addressed cache when valid."""
    factory = worker_factory or get_worker
    key = render_key(content_hash, design_hash, spec.platform, spec.template_version)
    cache = VideoCache(cache_root)
    destination = Path(output_root) / spec.platform / spec.filename
    poster_destination = Path(output_root) / spec.platform / spec.poster_filename

    cached_video = cache.read(key, spec.filename) if reuse_cache else None
    cached_poster = cache.read(key, spec.poster_filename) if reuse_cache else None
    cached_time = cache.read(key, "poster.txt") if reuse_cache else None

    warnings: list[str] = []
    if cached_video is not None and cached_poster is not None:
        _copy_if_changed(cached_video, destination)
        _copy_if_changed(cached_poster, poster_destination)
        timestamp = _cached_timestamp(cached_time, spec)
        probe = probe_video(destination)
        within = len(cached_video) <= spec.max_bytes
        if not within:
            warnings.append(
                f"{spec.platform} video exceeds the {spec.max_bytes} byte ceiling."
            )
        return RenderedVideoFile(
            platform=spec.platform,
            filename=spec.filename,
            poster_filename=spec.poster_filename,
            path=destination,
            poster_path=poster_destination,
            width=spec.size[0],
            height=spec.size[1],
            duration=spec.duration,
            fps=spec.fps,
            size=len(cached_video),
            poster_size=len(cached_poster),
            sha256=hashlib.sha256(cached_video).hexdigest(),
            poster_sha256=hashlib.sha256(cached_poster).hexdigest(),
            cache_key=key,
            cached=True,
            template_version=spec.template_version,
            poster_timestamp=timestamp,
            within_ceiling=within,
            probe=probe,
            warnings=tuple(warnings),
        )

    html = video_html(context, store=store, base_dir=base_dir)
    times = frame_times(spec.duration, spec.fps)
    if not times:
        raise VideoError("video duration produced no frames")

    cache.root.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f"snap-video-{spec.platform}-", dir=cache.root)
    )
    try:
        frames = capture_frames_parallel(
            html,
            spec.size[0],
            spec.size[1],
            times,
            workers=workers,
            worker_factory=factory,
        )
        expected = set(range(len(times)))
        if set(frames) != expected:
            missing = sorted(expected - set(frames))[:5]
            raise VideoError(f"frame capture missed indices: {missing}")
        frame_dir = temporary / "frames"
        write_frames(frames, frame_dir)
        encoded: EncodedVideo = encode_frames(frame_dir, temporary / spec.filename, spec)
        poster_data, poster_at, poster_blank = _poster_with_fallback(
            html, spec, worker_factory=factory
        )
        if poster_blank:
            warnings.append("poster is nearly flat; check the sign-off scene copy.")
        data = encoded.path.read_bytes()
        _ = encoded
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    cache.write(key, spec.filename, data)
    cache.write(key, spec.poster_filename, poster_data)
    cache.write(key, "poster.txt", f"{poster_at}".encode("ascii"))
    _copy_if_changed(data, destination)
    _copy_if_changed(poster_data, poster_destination)

    within = len(data) <= spec.max_bytes
    if not within:
        warnings.append(
            f"{spec.platform} video exceeds the {spec.max_bytes} byte ceiling."
        )
    return RenderedVideoFile(
        platform=spec.platform,
        filename=spec.filename,
        poster_filename=spec.poster_filename,
        path=destination,
        poster_path=poster_destination,
        width=spec.size[0],
        height=spec.size[1],
        duration=spec.duration,
        fps=spec.fps,
        size=len(data),
        poster_size=len(poster_data),
        sha256=hashlib.sha256(data).hexdigest(),
        poster_sha256=hashlib.sha256(poster_data).hexdigest(),
        cache_key=key,
        cached=False,
        template_version=spec.template_version,
        poster_timestamp=poster_at,
        within_ceiling=within,
        probe=probe_video(destination),
        warnings=tuple(warnings),
    )


def _cached_timestamp(raw: bytes | None, spec: VideoSpec) -> float:
    if raw is not None:
        try:
            return float(raw.decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            pass
    return poster_time(spec.duration)


# ---------------------------------------------------------------------------
# Run-level service
# ---------------------------------------------------------------------------


def _requested(names: list[str]):
    try:
        return video_specs_for(names)
    except KeyError as exc:
        raise VideoError(str(exc)) from exc


def render_run_videos(
    db: Session,
    run: Run,
    body: VideoIn,
    actor_id: str | None = None,
    *,
    worker_factory: Callable[[], ChromeWorker] | None = None,
) -> VideoOut:
    """Render every requested platform video and poster for a run."""
    model = _model(run)
    profile = _profile(run)
    design = _design(db, run)
    specs = _requested(body.platforms)
    if not specs:
        raise VideoError("no video platforms were requested")

    settings = get_settings()
    media_root = Path(settings.media_root)
    output_root = media_root / run.tenant_id / run.site_id / run.id / "videos"
    cache_root = media_root / "video-cache"
    store = AssetStore(
        cache_root / "assets",
        fetch_remote=bool(settings.render_fetch_remote),
    )
    content_hash = content_model_hash(run.content_model_json)
    design_hash = design_system_hash(design)

    warnings: list[str] = []
    files: list[RenderedVideoFile] = []
    for spec in specs:
        context = build_video_context(model, profile, design, spec)
        local_warnings = video_warnings(context, spec)
        rendered = render_video_asset(
            spec,
            context,
            content_hash=content_hash,
            design_hash=design_hash,
            output_root=output_root,
            cache_root=cache_root,
            workers=body.workers,
            reuse_cache=body.reuse_cache,
            store=store,
            worker_factory=worker_factory,
        )
        warnings.extend(local_warnings)
        warnings.extend(rendered.warnings)
        files.append(rendered)

    videos = [
        RenderedVideoOut(
            platform=item.platform,
            filename=item.filename,
            poster_filename=item.poster_filename,
            path=_relative(item.path, media_root),
            poster_path=_relative(item.poster_path, media_root),
            width=item.width,
            height=item.height,
            duration=item.duration,
            fps=item.fps,
            bytes=item.size,
            poster_bytes=item.poster_size,
            sha256=item.sha256,
            poster_sha256=item.poster_sha256,
            cache_key=item.cache_key,
            cached=item.cached,
            template_version=item.template_version,
            poster_timestamp=item.poster_timestamp,
            within_ceiling=item.within_ceiling,
            probe=VideoProbeOut.model_validate(item.probe),
        )
        for item in files
    ]

    stats = dict(run.stats_json or {})
    stats["video"] = {
        "renderer_version": VIDEO_RENDERER_VERSION,
        "content_model_hash": content_hash,
        "design_system_hash": design_hash,
        "cache_keys": sorted({item.cache_key for item in files}),
        "cache_hits": sum(1 for item in files if item.cached),
        "videos": [
            {
                "platform": item.platform,
                "filename": item.filename,
                "poster_filename": item.poster_filename,
                "bytes": item.size,
                "poster_bytes": item.poster_size,
                "sha256": item.sha256,
                "poster_sha256": item.poster_sha256,
                "duration": item.duration,
                "fps": item.fps,
                "within_ceiling": item.within_ceiling,
            }
            for item in files
        ],
    }
    run.stats_json = stats
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action="video.rendered",
            target_type="run",
            target_id=run.id,
            meta={
                "renderer_version": VIDEO_RENDERER_VERSION,
                "videos": [item.filename for item in files],
                "cache_hits": sum(1 for item in files if item.cached),
            },
        )
    )
    return VideoOut(
        run_id=run.id,
        content_model_hash=content_hash,
        design_system_hash=design_hash,
        renderer_version=VIDEO_RENDERER_VERSION,
        videos=videos,
        warnings=warnings,
        rendered_at=date.today(),
    )
