from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class VideoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platforms: list[str] = Field(default_factory=lambda: ["linkedin"], max_length=5)
    reuse_cache: bool = True
    workers: int = Field(default=2, ge=1, le=8)


class VideoProbeOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    codec_name: str | None = None
    width: int = 0
    height: int = 0
    pix_fmt: str | None = None
    color_range: str | None = None
    color_space: str | None = None
    color_primaries: str | None = None
    color_transfer: str | None = None
    r_frame_rate: str | None = None
    avg_frame_rate: str | None = None
    fps: float = 0.0
    duration: float = 0.0
    nb_frames: int = 0
    size: int = 0
    format_name: str | None = None


class RenderedVideoOut(BaseModel):
    platform: str
    filename: str
    poster_filename: str
    path: str
    poster_path: str
    width: int
    height: int
    duration: float
    fps: int
    bytes: int
    poster_bytes: int
    sha256: str
    poster_sha256: str
    cache_key: str
    cached: bool
    template_version: str
    poster_timestamp: float
    within_ceiling: bool
    probe: VideoProbeOut


class VideoOut(BaseModel):
    run_id: str
    content_model_hash: str
    design_system_hash: str
    renderer_version: str
    videos: list[RenderedVideoOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rendered_at: date
