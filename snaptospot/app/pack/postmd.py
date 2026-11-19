"""Write the nine-section ``post.md`` deck from design §11.

The template is fixed on purpose: every kit reads the same way, so a stranger
can open one file and publish without reading documentation. Counts are the
platform's own counts, not the raw string length.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.compose.layouts import CARD_ASSETS, CARD_LABELS
from app.copy.alt import AltResult
from app.copy.counts import count_for, spec_for_copy
from app.design.platforms import spec_for
from app.design.video import video_spec_for
from app.schemas.content import ContentModel, Fact
from app.schemas.copy import CopyDeck, PostSpec
from app.schemas.profile import SiteProfile

_LABELS = {
    "linkedin": "LinkedIn",
    "x": "X (Twitter)",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "whatsapp": "WhatsApp",
}

_LINK_NOTES = {
    "end": (
        "LinkedIn makes links clickable. Keep the URL as the last line of the post "
        "body."
    ),
    "last_tweet": (
        "X counts every URL as 23 characters. The hook carries no link; the URL "
        "belongs in the last tweet."
    ),
    "bio": (
        "This platform does not make caption links clickable. The URL lives in the "
        'bio; the caption says "link in bio".'
    ),
    "none": (
        "WhatsApp captions cannot carry a link. Send the URL as a message, never in "
        "a status caption."
    ),
}


def _platform(platform: str) -> str:
    return _LABELS.get(platform, platform.title())


def _fence(text: str) -> str:
    return f"```text\n{text.strip()}\n```"


def _count(spec: PostSpec, text: str) -> str:
    count = count_for(spec, text)
    return f"{count:,} characters"


def _still_line(platform: str) -> str:
    spec = spec_for(platform)
    return f"4 stills ({spec.size[0]} × {spec.size[1]})"


def _video_line(platform: str) -> str:
    try:
        video = video_spec_for(platform)
    except KeyError:
        return ""
    return (
        f"1 video ({video.size[0]} × {video.size[1]}, "
        f"{video.duration:g} s, silent)"
    )


def _used_facts(deck: CopyDeck, model: ContentModel) -> list[Fact]:
    """Tier-B facts that reached the copy: pointers plus literal values."""
    ids = {item.fact_id for item in model.proof}
    ids.update(
        offering.metric_fact_id
        for offering in model.offerings
        if offering.metric_fact_id
    )
    ids.update(
        project.badge_fact_id
        for project in model.projects
        if project.badge_fact_id
    )
    text = "\n".join(
        [
            deck.primary,
            *deck.alternatives,
            *(deck.thread or []),
            deck.short_variant,
            *(deck.messages or {}).values(),
        ]
    )
    used: list[Fact] = []
    for fact in model.facts:
        if fact.tier != "B":
            continue
        if fact.id in ids or (fact.value and fact.value in text):
            used.append(fact)
    return used


def _omissions(profile: SiteProfile) -> list[str]:
    lines: list[str] = []
    for gap in profile.gaps:
        reason = gap.reason or "no supporting source"
        lines.append(f"- `{gap.key}`: {reason} (class: {gap.gap_class}, status: {gap.status})")
    return lines


def _files(platform: str) -> list[str]:
    spec = spec_for(platform)
    try:
        video = video_spec_for(platform)
    except KeyError:
        video = None
    rows = ["| File | Use |", "| --- | --- |"]
    for card, name in CARD_ASSETS.items():
        rows.append(
            f"| `{name}.png` | {CARD_LABELS[card]} ({spec.size[0]} × {spec.size[1]}) |"
        )
    if video is not None:
        rows.append(
            f"| `{video.filename}` | {video.duration:g} s silent loop, "
            f"{video.size[0]} × {video.size[1]}, 30 fps, H.264 |"
        )
        rows.append(
            f"| `{video.poster_filename}` | Thumbnail / poster frame "
            f"({video.size[0]} × {video.size[1]}) |"
        )
    rows.append("| `post.md` | This copy deck |")
    rows.append("| `assets/cards.html` | Editable source for the stills |")
    rows.append("| `assets/video.html` | Editable, timeline-driven video source |")
    rows.append("| `assets/qr.png` | QR code used on the proof card |")
    return rows


def _checklist(platform: str) -> list[str]:
    if platform == "linkedin":
        return [
            "1. Upload the four images in order as a photo post, or upload the video "
            "on its own for more reach.",
            "2. Paste the primary copy. Keep the URL on the last line of the body.",
            "3. Add the alt text to each image before publishing.",
            "4. Pin a first comment with the project you are proudest of, or tag a collaborator.",
        ]
    if platform == "x":
        return [
            "1. Post the hook on its own. It must not contain the link.",
            "2. Post the four thread replies in order; the URL is in the last one.",
            "3. Attach an image to the replies so every tweet carries a visual.",
            "4. Keep the hashtags in the final tweet, not the hook.",
        ]
    if platform == "instagram":
        return [
            "1. Upload the four images in order as a single carousel.",
            "2. Add alt text to every slide before publishing.",
            "3. Put the portfolio link in the bio; the caption points there once.",
            "4. Post the Reel 24-48 hours later and set the poster frame as its cover.",
        ]
    if platform == "tiktok":
        return [
            "1. Upload the vertical video and keep the hook in the first 1.5 seconds.",
            "2. Use the caption above; the portfolio link goes in the bio.",
            "3. Keep text out of the right 120 px where the action rail sits.",
            "4. Pin a comment with the portfolio URL instead of putting it in the caption.",
        ]
    return [
        "1. Update your profile line to point at the portfolio.",
        "2. Post the status in the evening, when status views peak.",
        "3. Send the individual message to people you have actually worked with, not a bulk list.",
        "4. Post the share card in one or two relevant groups the next morning.",
        "5. Use the broadcast list only if people opted in.",
    ]


def _message_section(deck: CopyDeck, spec: PostSpec) -> list[str]:
    if not deck.messages:
        return []
    lines = ["## 3. Message shapes", ""]
    for shape in spec.shapes:
        text = deck.messages.get(shape)
        if not text:
            continue
        lines += [f"### {shape.title()}", "", _fence(text), "", _count(spec, text) + ".", ""]
    return lines


def render_post_md(
    platform: str,
    deck: CopyDeck,
    model: ContentModel,
    profile: SiteProfile,
    *,
    alt_blocks: list[AltResult] | None = None,
    run_id: str | None = None,
) -> str:
    """Render the fixed nine-section deck as Markdown text."""
    spec = spec_for_copy(platform)
    name = _platform(spec.platform)
    title = profile.entities.person.name or profile.entities.org.name or profile.title
    url = profile.url or model.cta.url
    alts = alt_blocks or []
    lines: list[str] = []

    # 1. Header
    lines += [
        f"# {name} launch kit - {title}",
        "",
        "## 1. Header",
        "",
        f"**Portfolio:** {url}",
        f"**Assets:** {_still_line(spec.platform)} + {_video_line(spec.platform)}",
        f"**Link:** {_LINK_NOTES[spec.link_policy]}",
        "",
    ]

    # 2. Recommended copy
    lines += [
        "## 2. Recommended copy",
        "",
        "### Primary",
        "",
        _fence(deck.primary),
        "",
        _count(spec, deck.primary)
        + f" (limit {spec.caption_max:,}).",
        "",
        "### Alternatives",
        "",
    ]
    for index, alternative in enumerate(deck.alternatives, start=1):
        lines += [
            f"**Alternative {index}** - {_count(spec, alternative)}",
            "",
            _fence(alternative),
            "",
        ]

    # 3. Thread / carousel / short variant / WhatsApp shapes
    if deck.thread:
        lines += ["## 3. Thread copy", ""]
        for index, tweet in enumerate(deck.thread, start=1):
            lines += [
                f"**Reply {index}** - {_count(spec, tweet)}",
                "",
                _fence(tweet),
                "",
            ]
    elif deck.messages:
        lines += _message_section(deck, spec)
    else:
        lines += [
            "## 3. Short variant",
            "",
            _fence(deck.short_variant),
            "",
            _count(spec, deck.short_variant) + ".",
            "",
        ]

    # 4. Video caption
    video_caption = deck.short_variant or deck.primary
    lines += ["## 4. Video caption", "", _fence(video_caption), ""]

    # 5. Alt text
    lines += ["## 5. Alt text", ""]
    if alts:
        for block in alts:
            filename = block.asset.split("/")[-1]
            lines += [f"**{filename}**", "", _fence(block.text), ""]
            for warning in block.warnings:
                lines += [f"- Warning: {warning}", ""]
    else:
        lines += [
            "No composed layouts were available when this deck was written. "
            "Compose the run, then rerun the copy command to fill this section.",
            "",
        ]
    try:
        video = video_spec_for(spec.platform)
    except KeyError:
        video = None
    if video is not None:
        lines += [
            "**Video description**",
            "",
            _fence(
                f"{video.duration:g}-second silent motion graphic, "
                f"{video.size[0]} × {video.size[1]}, 30 fps, H.264, no audio track. "
                f"{model.thesis}"
            ),
            "",
        ]

    # 6. Posting order and checklist
    lines += ["## 6. Posting order and checklist", ""]
    lines += _checklist(spec.platform)
    lines += [""]

    # 7. Files
    lines += ["## 7. Files", ""]
    lines += _files(spec.platform)
    lines += [""]

    # 8. Re-render commands
    rid = run_id or "<run-id>"
    lines += [
        "## 8. Re-render commands",
        "",
        "```text",
        f"python -m app.cli render --run {rid} --platform {spec.platform}",
        f"python -m app.cli video --run {rid} --platform {spec.platform}",
        f"python -m app.cli copy --run {rid} --platform {spec.platform}",
        "```",
        "",
        "To edit the prose, change this file. To edit the design, change "
        "`assets/cards.html` or `assets/video.html` and rerun the commands above.",
        "",
    ]

    # 9. Sources and omissions
    lines += ["## 9. Sources and omissions", ""]
    used = _used_facts(deck, model)
    lines += ["### Sources (tier B)", ""]
    if used:
        for fact in used:
            published = f", published {fact.published_at.isoformat()}" if fact.published_at else ""
            lines.append(
                f"- `{fact.id}` - {fact.value}"
                f"{' ' + fact.unit if fact.unit else ''} {fact.label or fact.key}: "
                f"{fact.source} (retrieved {fact.retrieved_at.isoformat()}{published})"
            )
    else:
        lines.append("- No tier-B facts reached this deck.")
    lines += ["", "### Omissions", ""]
    omissions = _omissions(profile)
    lines += omissions or ["- No omissions were recorded for this run."]
    if model.disclaimers:
        lines += [""]
        lines += [f"- Note: {note}" for note in model.disclaimers]
    lines += [
        "",
        "Facts with tier C or D are excluded from every asset and from this copy deck. "
        "If a number is absent here, the site did not support it with a tier A or B source.",
        "",
    ]

    return "\n".join(lines).rstrip() + "\n"


def write_post_md(path: Path | str, text: str) -> Path:
    """Write atomically so a failed run never leaves a half deck."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, destination)
    return destination
