import json
from typing import Any

from bs4 import BeautifulSoup


def load_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Return every JSON-LD node in a document, flattened from @graph."""
    nodes: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes.extend(_flatten(data))
    return nodes


def _flatten(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        out: list[dict[str, Any]] = []
        for item in data:
            out.extend(_flatten(item))
        return out
    if not isinstance(data, dict):
        return []
    out = [data]
    graph = data.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            out.extend(_flatten(item))
    return out


def node_types(node: dict[str, Any]) -> set[str]:
    value = node.get("@type", "")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()
