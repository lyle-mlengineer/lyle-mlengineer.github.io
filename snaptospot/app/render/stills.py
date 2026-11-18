"""Render LayoutAST cards to content-addressed PNG stills.

The cache key is the contract from the design document:

    (content_model_hash, design_system_hash, platform, template_version)

The key names a directory; each card inside it is stored under its §11 output
name. A second request for the same tuple is a disk read, not a browser visit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.compose.ast import grid_shape
from app.compose.layouts import CARD_ASSETS
from app.compose.templates import render_card, standalone
from app.design.platforms import ratio_class
from app.render.assets import AssetStore, prepare_document
from app.render.chrome import ChromeWorker, get_worker
from app.schemas.design import DesignSystem, LayoutAST

logger = logging.getLogger(__name__)

_CARD_BY_ASSET = {name: card for card, name in CARD_ASSETS.items()}


def _fetch_remote() -> bool:
    from app.config import get_settings

    return bool(get_settings().render_fetch_remote)


@dataclass(frozen=True)
class RenderedStill:
    asset: str
    filename: str
    path: Path
    width: int
    height: int
    sha256: str
    size: int
    cache_key: str
    cached: bool
    template_version: str


def card_for_asset(asset: str) -> str:
    name = asset.rsplit("/", 1)[-1]
    if name.endswith(".png"):
        name = name[:-4]
    try:
        return _CARD_BY_ASSET[name]
    except KeyError as exc:
        raise ValueError(f"Unknown card asset {asset!r}") from exc


def asset_filename(asset: str) -> str:
    name = asset.rsplit("/", 1)[-1]
    return name if name.endswith(".png") else f"{name}.png"


def canonical_hash(payload: Any) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def content_model_hash(model: Any) -> str:
    if hasattr(model, "model_dump"):
        model = model.model_dump(mode="json")
    return canonical_hash(model)


def render_key(
    content_hash: str,
    design_hash: str,
    platform: str,
    template_version: str,
) -> str:
    return canonical_hash(
        {
            "content_model_hash": content_hash,
            "design_system_hash": design_hash,
            "platform": platform,
            "template_version": template_version,
        }
    )


def layout_context(layout: LayoutAST, design: DesignSystem) -> dict[str, object]:
    card = card_for_asset(layout.asset)
    columns, rows = grid_shape(card, layout.template, layout.measured.density)
    return {
        "width": layout.width,
        "height": layout.height,
        "ratio_class": ratio_class(layout.ratio),
        "template": layout.template,
        "tokens": design.tokens.model_dump(mode="json"),
        "portrait_treatment": design.portrait_treatment.model_dump(mode="json"),
        "media_treatment": design.media_treatment.model_dump(mode="json"),
        "slots": layout.slots.model_dump(mode="json"),
        "cols": columns,
        "rows": rows,
    }


def layout_html(
    layout: LayoutAST,
    design: DesignSystem,
    *,
    store: AssetStore | None = None,
    base_dir: Path | str | None = None,
) -> str:
    card = card_for_asset(layout.asset)
    context = layout_context(layout, design)
    _resolve_slot_media(context, store)
    fragment = render_card(
        context,
        card,
        layout.measured.density,
        layout.measured.headline_pt,
    )
    document = standalone(fragment, layout.width, layout.height)
    return prepare_document(document, base_dir=base_dir, store=store)


def _resolve_slot_media(context: dict[str, object], store: AssetStore | None) -> None:
    """Drop media the capture cannot load instead of drawing an empty frame.

    A missing portrait should not become a grey square inside the ring; the
    template simply omits the portrait column when the slot list is empty.
    """
    if store is None:
        return
    slots = context.get("slots")
    if not isinstance(slots, dict):
        return
    media = slots.get("media")
    if isinstance(media, list):
        resolved_media = []
        for item in media:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            resolved = store.resolve(url, None)
            if resolved is not None:
                resolved_media.append({**item, "url": resolved})
        slots["media"] = resolved_media
    tiles = slots.get("tiles")
    if isinstance(tiles, list):
        for tile in tiles:
            if not isinstance(tile, dict) or not tile.get("image"):
                continue
            resolved = store.resolve(str(tile["image"]), None)
            tile["image"] = resolved



class RenderCache:
    """Content-addressed PNG store rooted at ``media_root/render-cache``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def directory(self, key: str) -> Path:
        return self.root / key[:2] / key

    def path(self, key: str, filename: str) -> Path:
        return self.directory(key) / filename

    def read(self, key: str, filename: str) -> bytes | None:
        path = self.path(key, filename)
        try:
            return path.read_bytes() if path.exists() else None
        except OSError:
            return None

    def write(self, key: str, filename: str, data: bytes) -> Path:
        path = self.path(key, filename)
        _write_atomic(path, data)
        return path


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def render_layout(
    layout: LayoutAST,
    design: DesignSystem,
    *,
    content_hash: str,
    design_hash: str,
    output_root: Path | str,
    cache_root: Path | str,
    worker: ChromeWorker | None = None,
    asset_store: AssetStore | None = None,
    use_cache: bool = True,
) -> RenderedStill:
    platform = layout.asset.split("/", 1)[0]
    filename = asset_filename(layout.asset)
    key = render_key(
        content_hash,
        design_hash,
        platform,
        layout.template_version,
    )
    cache = RenderCache(cache_root)
    data = cache.read(key, filename) if use_cache else None
    cached = data is not None
    if data is None:
        store = asset_store or AssetStore(
            Path(cache_root) / "assets",
            fetch_remote=_fetch_remote(),
        )
        html = layout_html(layout, design, store=store)
        renderer = worker or get_worker()
        data = renderer.capture(html, layout.width, layout.height).data
        cache.write(key, filename, data)

    destination = Path(output_root) / platform / filename
    if not destination.exists() or destination.read_bytes() != data:
        _write_atomic(destination, data)

    return RenderedStill(
        asset=layout.asset,
        filename=filename,
        path=destination,
        width=layout.width,
        height=layout.height,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        cache_key=key,
        cached=cached,
        template_version=layout.template_version,
    )


def render_layouts(
    layouts: list[LayoutAST],
    design: DesignSystem,
    *,
    content_hash: str,
    design_hash: str,
    output_root: Path | str,
    cache_root: Path | str,
    worker: ChromeWorker | None = None,
    asset_store: AssetStore | None = None,
    use_cache: bool = True,
) -> list[RenderedStill]:
    return [
        render_layout(
            layout,
            design,
            content_hash=content_hash,
            design_hash=design_hash,
            output_root=output_root,
            cache_root=cache_root,
            worker=worker,
            asset_store=asset_store,
            use_cache=use_cache,
        )
        for layout in layouts
    ]
