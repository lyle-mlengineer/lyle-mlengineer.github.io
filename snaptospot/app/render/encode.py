"""Encode JPEG frames to a deterministic, player-friendly H.264 MP4.

The colour range conversion is not optional. Canvas/JPEG frames are full range;
most players expect limited range. Without ``in_range=full:out_range=tv`` the ink
backgrounds wash out on some Android players.

Determinism comes from three things: frames are addressed by index, ffmpeg gets
``-bitexact`` flags and no metadata mapping, and the x264 settings are fixed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.schemas.design import VideoSpec


class EncodeError(RuntimeError):
    """ffmpeg or ffprobe was unavailable, or encoding failed."""


@dataclass(frozen=True)
class EncodedVideo:
    path: Path
    size: int
    sha256: str
    probe: dict[str, object]


def ffmpeg_binary() -> str:
    configured = shutil.which("ffmpeg")
    if configured is None:
        raise EncodeError("ffmpeg is not on PATH")
    return configured


def ffprobe_binary() -> str:
    configured = shutil.which("ffprobe")
    if configured is None:
        raise EncodeError("ffprobe is not on PATH")
    return configured


def encode_command(frames_dir: Path, output: Path, spec: VideoSpec) -> list[str]:
    """The exact ffmpeg invocation, exposed so tests can assert the flags."""
    return [
        ffmpeg_binary(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(spec.fps),
        "-start_number",
        "0",
        "-i",
        str(frames_dir / "f_%04d.jpg"),
        "-vf",
        "scale=in_range=full:out_range=tv:out_color_matrix=bt709",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_range",
        "tv",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "19",
        "-x264-params",
        "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-r",
        str(spec.fps),
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-map_metadata",
        "-1",
        "-an",
        str(output),
    ]


def encode_frames(frames_dir: Path | str, output: Path | str, spec: VideoSpec) -> EncodedVideo:
    """Encode ``f_0000.jpg`` onward into ``output`` and probe the result."""
    source = Path(frames_dir)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = encode_command(source, destination, spec)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise EncodeError(f"ffmpeg failed ({completed.returncode}): {detail[:600]}")
    data = destination.read_bytes()
    return EncodedVideo(
        path=destination,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        probe=probe_video(destination),
    )


def probe_video(path: Path | str) -> dict[str, object]:
    """Return the fields the platform spec gate asserts on."""
    command = [
        ffprobe_binary(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise EncodeError(f"ffprobe failed ({completed.returncode}): {detail[:600]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EncodeError("ffprobe returned invalid JSON") from exc

    streams = payload.get("streams") or []
    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        streams[0] if streams else {},
    )
    container = payload.get("format") or {}
    fps = _fraction(video.get("r_frame_rate")) or _fraction(video.get("avg_frame_rate"))
    duration = _number(container.get("duration")) or _number(video.get("duration"))
    return {
        "codec_name": video.get("codec_name"),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "pix_fmt": video.get("pix_fmt"),
        "color_range": video.get("color_range"),
        "color_space": video.get("color_space"),
        "color_primaries": video.get("color_primaries"),
        "color_transfer": video.get("color_transfer"),
        "r_frame_rate": video.get("r_frame_rate"),
        "avg_frame_rate": video.get("avg_frame_rate"),
        "fps": round(fps, 4),
        "duration": round(duration, 4),
        "nb_frames": _integer(video.get("nb_frames")),
        "size": _integer(container.get("size")),
        "format_name": container.get("format_name"),
    }


def _fraction(value: object) -> float:
    if not value:
        return 0.0
    text = str(value)
    if "/" not in text:
        return _number(text)
    numerator, denominator = text.split("/", 1)
    try:
        divisor = float(denominator)
        return float(numerator) / divisor if divisor else 0.0
    except (TypeError, ValueError):
        return 0.0


def _number(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _integer(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
