"""Deterministic video: timeline maths, frame capture, encoding, poster, HTTP."""

from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.compose import service as compose_service
from app.design.tokens import build_design_system
from app.design.video import (
    INSTAGRAM_VIDEO,
    LINKEDIN_VIDEO,
    TIKTOK_VIDEO,
    WHATSAPP_VIDEO,
    X_VIDEO,
    last_line_for,
    video_spec_for,
    video_specs_for,
)
from app.render.assets import AssetStore
from app.render.chrome import VIDEO_RENDERER_VERSION, ChromeWorker
from app.render.encode import encode_command, encode_frames, probe_video
from app.render.frames import (
    capture_frames_parallel,
    cubic_out,
    frame_times,
    out_back,
    poster_time,
    render_at_script,
    split_ranges,
    timeline_payload,
    write_frames,
)
from app.render.poster import capture_poster, frame_stats, is_blank
from app.render.stills import render_key
from app.render.video import (
    VideoCache,
    build_video_context,
    render_video_asset,
    video_html,
    video_warnings,
)
from app.schemas.design import VideoSpec
from tests.conftest import TestingSession, auth_headers
from tests.test_compose import RuleMeasurer, make_model, make_profile, seed_run

SIZE = (270, 270)


def short_spec(**overrides: object) -> VideoSpec:
    """A tiny spec so the render path can be exercised in seconds."""
    values: dict[str, object] = {
        "duration": 2,
        "fps": 10,
        "size": SIZE,
        "template_version": "video@test",
        "max_bytes": 10**9,
    }
    values.update(overrides)
    return video_spec_for("linkedin").model_copy(update=values)


def flat_png(color: tuple[int, int, int], *, art: bool = False) -> bytes:
    image = Image.new("RGB", (64, 64), color)
    if art:
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 40, 40], fill=(240, 240, 240))
        draw.rectangle([44, 44, 60, 60], fill=(190, 190, 190))
        draw.line([(4, 60), (60, 4)], fill=(120, 120, 120), width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Timeline and easing
# ---------------------------------------------------------------------------


def test_easing_has_exact_endpoints_and_no_jumps() -> None:
    assert cubic_out(0.0) == 0.0
    assert cubic_out(1.0) == 1.0
    values = [cubic_out(index / 20) for index in range(21)]
    assert values == sorted(values)

    assert out_back(0.0) == pytest.approx(0.0)
    assert out_back(1.0) == pytest.approx(1.0)
    assert out_back(0.5) > 0.5  # the overshoot is the point


def test_frame_times_come_from_the_index_not_a_clock() -> None:
    times = frame_times(15, 30)
    assert len(times) == 450
    assert times[0] == 0.0
    assert times[1] == pytest.approx(1 / 30)
    assert times[-1] == pytest.approx(449 / 30)
    assert frame_times(0, 30) == []
    assert frame_times(15, 0) == []


def test_poster_lands_before_the_last_frame() -> None:
    assert poster_time(15) == pytest.approx(14.2)
    assert poster_time(18) == pytest.approx(17.2)
    assert poster_time(0.5) == 0.0


def test_split_ranges_partition_every_index_exactly_once() -> None:
    for total in (1, 2, 5, 30, 450, 540):
        for workers in (1, 2, 3, 8):
            ranges = split_ranges(total, workers)
            assert ranges[0][0] == 0
            assert ranges[-1][1] == total
            assert all(end > start for start, end in ranges)
            assert all(
                ranges[index][1] == ranges[index + 1][0]
                for index in range(len(ranges) - 1)
            )
            assert sum(end - start for start, end in ranges) == total

    assert split_ranges(0, 2) == []
    assert split_ranges(3, 8) == [(0, 1), (1, 2), (2, 3)]


def test_timeline_crossfades_scene_boundaries() -> None:
    payload = timeline_payload(15)
    scenes = payload["scenes"]
    assert [scene["key"] for scene in scenes] == ["A", "B", "C", "D"]
    assert scenes[0]["start"] == 0.0
    for previous, following in zip(scenes, scenes[1:], strict=False):
        assert following["start"] < previous["out"]
    assert scenes[-1]["out"] > 1_000_000

    with_hook = timeline_payload(21, hook=True)
    assert with_hook["scenes"][0]["key"] == "Hook"
    assert with_hook["scenes"][1]["start"] < with_hook["scenes"][0]["out"]


def test_render_script_is_pure_and_embeds_the_timeline() -> None:
    script = render_at_script(duration=15, fps=30)
    assert "window.renderAt" in script
    assert "Date.now" not in script
    assert "Math.random" not in script
    assert "requestAnimationFrame" not in script
    payload = json.loads(script.split("var T = ", 1)[1].split(";", 1)[0])
    assert payload["duration"] == 15
    assert payload["fps"] == 30
    assert payload["scenes"][0]["key"] == "A"


def test_capture_reassembles_by_index_when_ranges_finish_out_of_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.render.frames as frames_module

    def fake_range(*_args: object, **_kwargs: object) -> dict[int, bytes]:
        start = int(_args[4])
        end = int(_args[5])
        if start == 0:
            time.sleep(0.05)  # let the later ranges finish first
        return {index: str(index).encode() for index in range(start, end)}

    monkeypatch.setattr(frames_module, "_capture_range", fake_range)
    times = [index / 10 for index in range(20)]
    frames = capture_frames_parallel("", 1, 1, times, workers=4)
    assert list(frames) == list(range(20))
    assert all(frames[index] == str(index).encode() for index in range(20))


# ---------------------------------------------------------------------------
# Platform registry
# ---------------------------------------------------------------------------


def test_video_registry_matches_the_playbook() -> None:
    assert LINKEDIN_VIDEO.size == (1080, 1080)
    assert LINKEDIN_VIDEO.duration == 15
    assert X_VIDEO.size == (1920, 1080)
    assert X_VIDEO.duration == 15
    assert INSTAGRAM_VIDEO.size == (1080, 1920)
    assert INSTAGRAM_VIDEO.duration == 18
    assert TIKTOK_VIDEO.duration == 21
    assert WHATSAPP_VIDEO.duration == 18

    assert INSTAGRAM_VIDEO.filename == "reel.mp4"
    assert INSTAGRAM_VIDEO.poster_filename == "reel-poster.png"
    assert WHATSAPP_VIDEO.filename == "status-video.mp4"
    assert WHATSAPP_VIDEO.max_bytes == 16 * 1024**2

    assert video_spec_for("linkedin") is LINKEDIN_VIDEO
    assert video_spec_for(LINKEDIN_VIDEO.id) is LINKEDIN_VIDEO
    assert [
        spec.platform for spec in video_specs_for(["linkedin", "linkedin", "whatsapp"])
    ] == ["linkedin", "whatsapp"]
    with pytest.raises(KeyError):
        video_spec_for("myspace")


@pytest.mark.parametrize(
    ("spec", "kind", "value"),
    [
        (LINKEDIN_VIDEO, "url", "https://lyle.example/work"),
        (X_VIDEO, "url", "https://lyle.example/work"),
        (INSTAGRAM_VIDEO, "bio", "Link in bio"),
        (TIKTOK_VIDEO, "follow", "Follow the build"),
        (WHATSAPP_VIDEO, "reply", "Reply YES"),
    ],
)
def test_last_line_is_platform_specific(
    spec: VideoSpec, kind: str, value: str
) -> None:
    line = last_line_for(spec, "https://lyle.example/work")
    assert line.kind == kind
    assert line.value == value


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def video_context(spec: VideoSpec) -> dict[str, object]:
    profile = make_profile()
    model = make_model()
    design = build_design_system(profile, "editorial_dark")
    return build_video_context(model, profile, design, spec)


def test_context_keeps_the_hero_short_and_the_caption_distinct() -> None:
    context = video_context(LINKEDIN_VIDEO)
    scene_a = context["scenes"]["a"]
    hook = scene_a["headline"][0]["text"]

    assert ":" not in hook
    assert len(hook) <= 52
    assert scene_a["caption"] != scene_a["subhead"]
    assert 70 <= int(context["hero_size"]) <= 148
    assert len(context["scenes"]["b"]["tiles"]) <= 4
    assert all(
        stat["tier"] in {"A", "B"} for stat in context["scenes"]["c"]["stats"]
    )


def test_hero_size_shrinks_as_the_hook_grows() -> None:
    from app.render.video import _hero_size as hero_size

    short = hero_size("Ship speech AI", 1080, "1:1")
    long = hero_size(" ".join(["speech"] * 30), 1080, "1:1")
    portrait = hero_size("Ship speech AI", 1080, "9:16")
    assert short == 148
    assert long < short
    assert portrait >= 72


def test_video_warnings_name_the_missing_evidence() -> None:
    context = video_context(LINKEDIN_VIDEO)
    context["scenes"]["b"]["tiles"] = []
    context["scenes"]["c"]["stats"] = []
    context["scenes"]["d"]["portrait"] = None
    warnings = video_warnings(context, LINKEDIN_VIDEO)
    assert any("capabilities" in warning for warning in warnings)
    assert any("stats" in warning for warning in warnings)
    assert any("portrait" in warning for warning in warnings)


# ---------------------------------------------------------------------------
# HTML and poster helpers
# ---------------------------------------------------------------------------


def test_video_html_is_self_contained(tmp_path: Path) -> None:
    context = video_context(LINKEDIN_VIDEO)
    document = video_html(
        context,
        store=AssetStore(tmp_path / "assets", fetch_remote=False),
    )
    assert "Content-Security-Policy" in document
    assert "default-src 'none'" in document
    assert "<script>" in document
    assert "window.renderAt" in document
    assert 'id="progress"' in document
    assert "data-enter" in document
    assert "fonts.googleapis" not in document
    assert "Bahnschrift" in document


def test_blank_detection_rejects_a_flat_frame_and_accepts_art() -> None:
    flat = flat_png((10, 10, 10))
    art = flat_png((10, 10, 10), art=True)
    assert frame_stats(flat)["dominant"] > 0.98
    assert is_blank(flat)
    assert not is_blank(art)

def test_size_ceiling_is_reported_on_a_cache_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = short_spec(max_bytes=10)
    key = render_key("content", "design", spec.platform, spec.template_version)
    cache = VideoCache(tmp_path / "cache")
    cache.write(key, spec.filename, b"x" * 100)
    cache.write(key, spec.poster_filename, flat_png((1, 2, 3), art=True))
    cache.write(key, "poster.txt", b"1.0")

    monkeypatch.setattr(
        "app.render.video.probe_video",
        lambda _path: {"codec_name": "h264", "width": 270, "height": 270},
    )
    rendered = render_video_asset(
        spec,
        {},
        content_hash="content",
        design_hash="design",
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        reuse_cache=True,
    )
    assert rendered.cached is True
    assert rendered.within_ceiling is False
    assert any("ceiling" in warning for warning in rendered.warnings)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def test_encode_command_is_the_design_contract(tmp_path: Path) -> None:
    command = encode_command(tmp_path / "frames", tmp_path / "out.mp4", LINKEDIN_VIDEO)
    assert "scale=in_range=full:out_range=tv:out_color_matrix=bt709" in command
    assert (
        "colorprim=bt709:transfer=bt709:colormatrix=bt709" in command
    )
    assert command[command.index("-crf") + 1] == "19"
    assert command[command.index("-preset") + 1] == "slow"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-r") + 1] == "30"
    assert command[command.index("-map_metadata") + 1] == "-1"
    assert "+faststart" in command
    assert "+bitexact" in command
    assert "-an" in command
    assert str(tmp_path / "frames" / "f_%04d.jpg") in command


# ---------------------------------------------------------------------------
# Real frames, real ffmpeg
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def worker() -> ChromeWorker:
    try:
        instance = ChromeWorker()
    except Exception as exc:  # noqa: BLE001 - skip on machines without Chromium
        pytest.skip(f"Chromium unavailable: {exc}")
    yield instance
    instance.close()


@pytest.fixture(scope="module")
def spec() -> VideoSpec:
    return short_spec()


@pytest.fixture(scope="module")
def document(tmp_path_factory: pytest.TempPathFactory, spec: VideoSpec) -> str:
    root = tmp_path_factory.mktemp("video-assets")
    context = video_context(spec)
    return video_html(context, store=AssetStore(root, fetch_remote=False))


@pytest.fixture(scope="module")
def encoded(
    document: str,
    spec: VideoSpec,
    worker: ChromeWorker,
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[list[float], dict[int, bytes], Path]:
    times = frame_times(spec.duration, spec.fps)
    frames = capture_frames_parallel(
        document,
        spec.size[0],
        spec.size[1],
        times,
        workers=1,
        worker_factory=lambda: worker,
    )
    root = tmp_path_factory.mktemp("video-encode")
    write_frames(frames, root / "frames")
    result = encode_frames(root / "frames", root / "out.mp4", spec)
    return times, frames, result.path


def test_same_timeline_produces_same_frame_hashes(
    document: str,
    spec: VideoSpec,
    worker: ChromeWorker,
    encoded: tuple[list[float], dict[int, bytes], Path],
) -> None:
    times, first, _ = encoded
    second = capture_frames_parallel(
        document,
        spec.size[0],
        spec.size[1],
        times,
        workers=1,
        worker_factory=lambda: worker,
    )
    assert sorted(first) == sorted(second) == list(range(len(times)))
    assert all(first[index] == second[index] for index in first)
    assert all(first[index][:2] == b"\xff\xd8" for index in first)


def test_same_frames_produce_the_same_mp4_hash(
    encoded: tuple[list[float], dict[int, bytes], Path],
    spec: VideoSpec,
    tmp_path: Path,
) -> None:
    _, _, first_path = encoded
    write_frames(encoded[1], tmp_path / "frames")
    second = encode_frames(tmp_path / "frames", tmp_path / "second.mp4", spec)
    assert second.path.read_bytes() == first_path.read_bytes()
    assert second.sha256 == hashlib.sha256(first_path.read_bytes()).hexdigest()
    assert second.size == first_path.stat().st_size


def test_ffprobe_reports_a_bt709_limited_range_mp4(
    encoded: tuple[list[float], dict[int, bytes], Path], spec: VideoSpec
) -> None:
    _, _, path = encoded
    probe = probe_video(path)
    assert probe["codec_name"] == "h264"
    assert (probe["width"], probe["height"]) == spec.size
    assert probe["pix_fmt"] == "yuv420p"
    assert probe["color_range"] == "tv"
    assert probe["color_space"] == "bt709"
    assert probe["color_primaries"] == "bt709"
    assert probe["color_transfer"] == "bt709"
    assert probe["fps"] == pytest.approx(spec.fps)
    assert probe["duration"] == pytest.approx(spec.duration, abs=0.05)
    assert probe["nb_frames"] == len(frame_times(spec.duration, spec.fps))


def test_poster_is_a_composed_frame_not_a_blank_first_frame(
    document: str, spec: VideoSpec, worker: ChromeWorker
) -> None:
    poster = capture_poster(document, spec, worker=worker)
    assert poster.timestamp == pytest.approx(spec.duration - 0.8)
    assert (poster.width, poster.height) == spec.size
    assert poster.blank is False
    assert frame_stats(poster.data)["stddev"] > 3.0
    with Image.open(io.BytesIO(poster.data)) as image:
        assert image.size == spec.size
        assert image.mode == "RGB"


def test_cached_video_reuses_bytes_without_a_browser(
    document: str,
    spec: VideoSpec,
    worker: ChromeWorker,
    tmp_path: Path,
) -> None:
    context = video_context(spec)
    first = render_video_asset(
        spec,
        context,
        content_hash="content",
        design_hash="design",
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        workers=1,
        reuse_cache=False,
        worker_factory=lambda: worker,
    )
    assert first.cached is False

    def exploding_factory() -> ChromeWorker:
        raise AssertionError("a cache hit must not launch Chromium")

    second = render_video_asset(
        spec,
        context,
        content_hash="content",
        design_hash="design",
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        workers=1,
        reuse_cache=True,
        worker_factory=exploding_factory,
    )
    assert second.cached is True
    assert second.sha256 == first.sha256
    assert second.poster_sha256 == first.poster_sha256


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


def test_video_endpoint_requires_auth(client: TestClient) -> None:
    assert client.post("/v1/runs/anything/videos", json={}).status_code == 401


def test_video_before_analyze_is_409(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)
        run.content_model_json = None
        db.commit()

    response = client.post(
        f"/v1/runs/{run.id}/videos", json={}, headers=auth_headers(pair)
    )
    assert response.status_code == 409, response.text
    assert "content model" in response.json()["detail"]


def test_video_is_tenant_scoped(client: TestClient, signup) -> None:
    ada = signup()
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    tenant_id = client.get("/v1/me", headers=auth_headers(ada)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/videos", json={}, headers=auth_headers(marcus)
    )
    assert response.status_code == 404


def test_unknown_video_platform_is_422(
    client: TestClient, signup, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.render.video as video_module

    monkeypatch.setattr(
        video_module,
        "_design",
        lambda _db, _run: build_design_system(make_profile(), "editorial_dark"),
    )
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/videos",
        json={"platforms": ["myspace"]},
        headers=auth_headers(pair),
    )
    assert response.status_code == 422, response.text
    assert "myspace" in response.json()["detail"]


def test_video_endpoint_writes_a_short_mp4_and_poster(
    client: TestClient,
    signup,
    monkeypatch: pytest.MonkeyPatch,
    worker: ChromeWorker,
) -> None:
    import app.render.video as video_module

    tiny = short_spec()
    monkeypatch.setattr(
        video_module, "video_specs_for", lambda _names: [tiny]
    )
    monkeypatch.setattr(
        video_module,
        "_design",
        lambda _db, _run: build_design_system(make_profile(), "editorial_dark"),
    )
    monkeypatch.setattr(
        compose_service,
        "make_measurer",
        lambda: (RuleMeasurer(lambda density, size: True), True),
    )

    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    first = client.post(
        f"/v1/runs/{run.id}/videos",
        json={"platforms": ["linkedin"], "workers": 1},
        headers=auth_headers(pair),
    )
    assert first.status_code == 200, first.text
    report = first.json()
    assert report["renderer_version"] == VIDEO_RENDERER_VERSION
    assert len(report["videos"]) == 1
    item = report["videos"][0]
    assert item["platform"] == "linkedin"
    assert item["filename"] == "launch-video.mp4"
    assert (item["width"], item["height"]) == SIZE
    assert item["duration"] == tiny.duration
    assert item["fps"] == tiny.fps
    assert item["cached"] is False
    assert item["within_ceiling"] is True
    assert item["probe"]["codec_name"] == "h264"
    assert item["probe"]["pix_fmt"] == "yuv420p"
    assert item["bytes"] > 0
    assert item["poster_bytes"] > 0
    assert item["poster_timestamp"] == pytest.approx(tiny.duration - 0.8)

    second = client.post(
        f"/v1/runs/{run.id}/videos",
        json={"platforms": ["linkedin"], "workers": 1},
        headers=auth_headers(pair),
    )
    assert second.status_code == 200, second.text
    cached = second.json()["videos"][0]
    assert cached["cached"] is True
    assert cached["sha256"] == item["sha256"]
    assert cached["poster_sha256"] == item["poster_sha256"]
