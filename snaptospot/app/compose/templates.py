"""Render one card AST context with the shared Jinja macros."""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "asset_templates"


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )


@lru_cache(maxsize=1)
def _module() -> object:
    return _environment().get_template("cards.html").module


def render_card(
    context: dict[str, object],
    card_id: str,
    density: int,
    headline_pt: int,
) -> str:
    module = _module()
    return str(module.card(context, card_id, density, headline_pt))


def standalone(html: str, width: int, height: int) -> str:
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<style>html,body{{margin:0;padding:0;width:{width}px;height:{height}px;"
        "overflow:hidden;background:#000;}}</style></head><body>"
        f"{html}</body></html>"
    )
