"""Generate the copy deck for a run and write one ``post.md`` per platform."""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.copy.counts import copy_specs_for, count_for
from app.copy.deck import (
    PROMPT_VERSION,
    CopyValidationError,
    generate_deck,
    prompt_hash,
    validate_deck,
)
from app.copy.voice import build_voice_card
from app.models import AuditLog, Run
from app.pack.postmd import render_post_md, write_post_md
from app.pipeline.understand.llm import LLMClient, LLMError
from app.schemas.content import ContentModel
from app.schemas.copy import (
    CopyDeck,
    CopyIn,
    CopyOut,
    RenderedCopyOut,
    VoiceCard,
)
from app.schemas.design import LayoutAST
from app.schemas.profile import SiteProfile

logger = logging.getLogger(__name__)


class CopyError(ValueError):
    """A run cannot produce copy, or a platform name is unknown."""


class CopyFirstError(CopyError):
    """The run has no content model or profile yet."""


def _model(run: Run) -> ContentModel:
    if not run.content_model_json:
        raise CopyFirstError("run has no content model; analyze the site first")
    try:
        return ContentModel.model_validate(run.content_model_json)
    except ValueError as exc:
        raise CopyError("run content model is invalid; re-analyze the site") from exc


def _profile(run: Run) -> SiteProfile:
    if not run.profile_json:
        raise CopyFirstError("run has no site profile; analyze the site first")
    try:
        return SiteProfile.model_validate(run.profile_json)
    except ValueError as exc:
        raise CopyError("run profile is invalid; re-analyze the site") from exc


def _layouts(run: Run) -> list[LayoutAST]:
    """Composed layouts are optional; copy can run before rendering."""
    stats = dict(run.stats_json or {})
    raw = (stats.get("compose") or {}).get("layouts") or []
    layouts: list[LayoutAST] = []
    for item in raw:
        try:
            layouts.append(LayoutAST.model_validate(item))
        except ValueError:
            continue
    return layouts


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _alt_blocks(
    deck: CopyDeck,
    layouts: list[LayoutAST],
    profile: SiteProfile,
):
    from app.copy.alt import AltResult, build_alts

    selected = [
        layout for layout in layouts if layout.asset.split("/", 1)[0] == deck.platform
    ]
    if not selected:
        return [], []
    blocks = build_alts(selected, profile=profile)
    warnings = [warning for block in blocks for warning in block.warnings]
    return (
        [AltResult(asset=block.asset, text=block.text) for block in blocks],
        warnings,
    )


def copy_run(
    db: Session,
    run: Run,
    body: CopyIn,
    actor_id: str | None = None,
    *,
    client: LLMClient | None = None,
) -> CopyOut:
    """Write a validated copy deck for every requested platform."""
    model = _model(run)
    profile = _profile(run)
    try:
        specs = copy_specs_for(body.platforms)
    except KeyError as exc:
        raise CopyError(str(exc)) from exc
    if not specs:
        raise CopyError("no copy platforms were requested")

    settings = get_settings()
    media_root = Path(settings.media_root)
    output_root = media_root / run.tenant_id / run.site_id / run.id / "posts"
    voice: VoiceCard = build_voice_card(profile, model)
    layouts = _layouts(run)
    llm = client if client is not None else LLMClient()
    use_llm = bool(body.use_llm)

    warnings: list[str] = []
    decks: list[CopyDeck] = []
    files: list[RenderedCopyOut] = []

    for spec in specs:
        try:
            deck = generate_deck(
                spec.platform,
                model,
                profile,
                voice=voice,
                client=llm,
                use_llm=use_llm,
            )
        except CopyValidationError:
            raise
        except (LLMError, ValueError, TypeError) as exc:
            raise CopyError(f"{spec.platform}: {exc}") from exc

        issues = validate_deck(deck, spec, model)
        if issues:
            raise CopyValidationError(issues)
        blocks, alt_warnings = _alt_blocks(deck, layouts, profile)
        deck = deck.model_copy(update={"alt_text": [block.text for block in blocks]})
        warnings.extend(deck.warnings)
        warnings.extend(alt_warnings)

        text = render_post_md(
            spec.platform,
            deck,
            model,
            profile,
            alt_blocks=blocks,
            run_id=run.id,
        )
        destination = write_post_md(output_root / spec.platform / "post.md", text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

        decks.append(deck)
        files.append(
            RenderedCopyOut(
                platform=spec.platform,
                path=_relative(destination, media_root),
                primary_chars=count_for(spec, deck.primary),
                alternative_chars=[
                    count_for(spec, alternative)
                    for alternative in deck.alternatives
                ],
                thread_chars=[
                    count_for(spec, tweet) for tweet in (deck.thread or [])
                ],
                short_chars=count_for(spec, deck.short_variant),
                hashtags=deck.hashtags,
                source=deck.source,
                validated=True,
                sha256=digest,
            )
        )

    stats = dict(run.stats_json or {})
    stats["copy"] = {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "voice": voice.model_dump(mode="json"),
        "decks": [
            {
                "platform": item.platform,
                "path": item.path,
                "primary_chars": item.primary_chars,
                "alternative_chars": item.alternative_chars,
                "thread_chars": item.thread_chars,
                "short_chars": item.short_chars,
                "hashtags": item.hashtags,
                "source": item.source,
                "sha256": item.sha256,
            }
            for item in files
        ],
    }
    run.stats_json = stats
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action="copy.generated",
            target_type="run",
            target_id=run.id,
            meta={
                "prompt_version": PROMPT_VERSION,
                "platforms": [item.platform for item in files],
                "sources": sorted({item.source for item in files}),
            },
        )
    )
    return CopyOut(
        run_id=run.id,
        voice=voice,
        decks=decks,
        files=files,
        warnings=warnings,
        generated_at=date.today(),
    )
