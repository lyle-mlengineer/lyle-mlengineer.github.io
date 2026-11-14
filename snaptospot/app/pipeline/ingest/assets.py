import colorsys
import hashlib
import logging
import math
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.pipeline.ingest.jsonld import load_jsonld
from app.schemas.profile import ColorToken, FontToken, ImageAsset, LogoAsset

logger = logging.getLogger(__name__)

_SKIP_SCHEMES = ("data:", "javascript:", "mailto:", "tel:", "blob:")
_GENERIC_FONTS = {
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
    "inherit",
    "initial",
    "unset",
    "revert",
}
_LOGO_HINTS = ("logo", "brand", "wordmark", "emblem")
_PORTRAIT_HINTS = ("portrait", "headshot", "avatar", "profile", "about-me", "me.jpg")
_PRODUCT_HINTS = ("screenshot", "dashboard", "product", "app-preview", "interface", "ui-")
_STOCK_HOSTS = ("unsplash.com", "pexels.com", "pixabay.com", "shutterstock.com")
_ICON_HINTS = ("icon", "favicon", "sprite")


def absolute_url(candidate: str, base_url: str) -> str | None:
    candidate = candidate.strip()
    if not candidate or candidate.startswith(_SKIP_SCHEMES):
        return None
    resolved = urljoin(base_url, candidate)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return resolved


def _srcset_best(srcset: str) -> str:
    best = ""
    best_weight = -1.0
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        candidate = bits[0]
        weight = 1.0
        if len(bits) > 1:
            descriptor = bits[1].lower()
            try:
                if descriptor.endswith("w"):
                    weight = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    weight = float(descriptor[:-1]) * 1000
            except ValueError:
                weight = 1.0
        if weight > best_weight:
            best, best_weight = candidate, weight
    return best


def _dimensions(node: Tag) -> tuple[int | None, int | None]:
    try:
        width = int(float(str(node.get("width")))) if node.get("width") else None
    except ValueError:
        width = None
    try:
        height = int(float(str(node.get("height")))) if node.get("height") else None
    except ValueError:
        height = None
    return width, height


def classify_image(url: str, alt: str, width: int | None, height: int | None) -> str:
    haystack = f"{url} {alt}".lower()
    host = (urlparse(url).hostname or "").lower()
    if any(host.endswith(stock) for stock in _STOCK_HOSTS):
        return "stock"
    if any(hint in haystack for hint in _LOGO_HINTS):
        return "logo"
    if any(hint in haystack for hint in _PORTRAIT_HINTS):
        return "portrait"
    if any(hint in haystack for hint in _PRODUCT_HINTS):
        return "product_shot"
    if any(hint in haystack for hint in _ICON_HINTS):
        return "icon"
    if width is not None and height is not None:
        if width <= 64 and height <= 64:
            return "icon"
        if 0.85 <= width / max(height, 1) <= 1.18 and width >= 200:
            return "unknown"
    return "unknown"


def _asset_id(url: str) -> str:
    return "img_" + hashlib.sha1(url.encode()).hexdigest()[:8]  # noqa: S324


def harvest_images(soup: BeautifulSoup, base_url: str) -> list[ImageAsset]:
    """Collect candidate images from markup, OG tags and JSON-LD."""
    found: dict[str, ImageAsset] = {}

    def add(candidate: str | None, alt: str = "", width: int | None = None,
            height: int | None = None) -> None:
        if not candidate:
            return
        resolved = absolute_url(candidate, base_url)
        if resolved is None or resolved in found:
            return
        found[resolved] = ImageAsset(
            asset_id=_asset_id(resolved),
            url=resolved,
            role=classify_image(resolved, alt, width, height),
            w=width,
            h=height,
            alt=alt or None,
        )

    for node in soup.find_all("img"):
        source = node.get("src") or node.get("data-src") or node.get("data-lazy-src")
        if node.get("srcset"):
            source = _srcset_best(str(node.get("srcset"))) or source
        width, height = _dimensions(node)
        add(str(source) if source else None, str(node.get("alt") or ""), width, height)

    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or "").lower()
        if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            add(str(meta.get("content") or ""), "social preview")

    for node in load_jsonld(soup):
        image = node.get("image")
        if isinstance(image, str):
            add(image)
        elif isinstance(image, list):
            for item in image:
                if isinstance(item, str):
                    add(item)
                elif isinstance(item, dict):
                    add(str(item.get("url") or item.get("contentUrl") or ""))
        elif isinstance(image, dict):
            add(str(image.get("url") or image.get("contentUrl") or ""))

    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel and link.get("href"):
            add(str(link.get("href")), "site icon")

    return list(found.values())[:200]


def harvest_fonts(soup: BeautifulSoup, html: str) -> list[FontToken]:
    families: list[str] = []

    def add(family: str) -> None:
        name = family.strip().strip("'\"")
        if not name or name.lower() in _GENERIC_FONTS or name.startswith("var("):
            return
        if name.lower() not in {existing.lower() for existing in families}:
            families.append(name)

    for link in soup.find_all("link"):
        href = str(link.get("href") or "")
        if "fonts.googleapis.com" not in href:
            continue
        for match in re.finditer(r"family=([^&]+)", href):
            for family in match.group(1).split("|"):
                add(family.split(":")[0].replace("+", " "))

    for match in re.finditer(r"font-family\s*:\s*([^;}\n]+)", html, flags=re.IGNORECASE):
        first = match.group(1).split(",")[0]
        add(first)

    fonts: list[FontToken] = []
    for index, family in enumerate(families[:6]):
        role = "display" if index == 0 else ("body" if index == 1 else "unknown")
        fonts.append(FontToken(family=family, role=role))
    return fonts


def _srgb_to_oklab(red: int, green: int, blue: int) -> tuple[float, float, float]:
    def linear(channel: float) -> float:
        channel /= 255.0
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = linear(red), linear(green), linear(blue)
    lum = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (lum, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def _role(lightness: float, chroma: float) -> str:
    if chroma >= 0.055 and 0.32 <= lightness <= 0.82:
        return "accent"
    if lightness < 0.25:
        return "ink"
    if lightness > 0.9:
        return "background"
    return "neutral"


def _cluster(colors: list[tuple[int, int, int, int]], limit: int) -> list[ColorToken]:
    """Merge perceptually close colours and return the heaviest ones."""
    clusters: list[dict[str, object]] = []
    total = sum(count for *_, count in colors) or 1
    for red, green, blue, count in colors:
        lab = _srgb_to_oklab(red, green, blue)
        for cluster in clusters:
            other = cluster["lab"]
            assert isinstance(other, tuple)
            distance = math.dist(lab, other)
            if distance < 0.12:
                cluster["count"] = int(cluster["count"]) + count  # type: ignore[arg-type]
                break
        else:
            clusters.append({"rgb": (red, green, blue), "lab": lab, "count": count})

    ranked = sorted(clusters, key=lambda item: int(item["count"]), reverse=True)
    tokens: list[ColorToken] = []
    for cluster in ranked[:limit]:
        red, green, blue = cluster["rgb"]  # type: ignore[misc]
        lab = cluster["lab"]
        assert isinstance(lab, tuple)
        tokens.append(
            ColorToken(
                hex=_hex(red, green, blue),
                role=_role(lab[0], math.hypot(lab[1], lab[2])),
                area=round(int(cluster["count"]) / total, 4),
            )
        )
    return tokens


def palette_from_image(path: str | Path, limit: int = 6) -> list[ColorToken]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - pillow is a hard dependency
        return []
    try:
        image = Image.open(path).convert("RGB").resize((160, 160))
    except Exception as exc:  # noqa: BLE001 - a bad screenshot is not fatal
        logger.info("Could not read screenshot for palette: %s", exc)
        return []

    counts: dict[tuple[int, int, int], int] = {}
    for red, green, blue in image.getdata():
        key = (red // 16 * 16, green // 16 * 16, blue // 16 * 16)
        counts[key] = counts.get(key, 0) + 1
    colors = [(r, g, b, count) for (r, g, b), count in counts.items()]
    return _cluster(colors, limit)


def palette_from_css(html: str, limit: int = 6) -> list[ColorToken]:
    counts: dict[tuple[int, int, int], int] = {}
    for match in re.finditer(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", html):
        value = match.group(1)
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
        key = (red // 16 * 16, green // 16 * 16, blue // 16 * 16)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return []
    colors = [(r, g, b, count) for (r, g, b), count in counts.items()]
    return _cluster(colors, limit)


def harvest_palette(screenshot_path: str | None, html: str) -> list[ColorToken]:
    if screenshot_path and Path(screenshot_path).exists():
        tokens = palette_from_image(screenshot_path)
        if tokens:
            return tokens
    return palette_from_css(html)


def pick_logo(
    images: list[ImageAsset],
    soup: BeautifulSoup,
    base_url: str,
) -> LogoAsset | None:
    for image in images:
        if image.role == "logo":
            return _logo_from(image.url, image.asset_id)
    for image in images:
        if image.role == "icon":
            return _logo_from(image.url, image.asset_id)
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel and link.get("href"):
            resolved = absolute_url(str(link.get("href")), base_url)
            if resolved:
                return _logo_from(resolved, _asset_id(resolved))
    return None


def _logo_from(url: str, asset_id: str) -> LogoAsset:
    suffix = urlparse(url).path.lower()
    return LogoAsset(
        asset_id=asset_id,
        url=url,
        transparent=True if suffix.endswith((".svg", ".png", ".webp")) else None,
    )


def dominant_lightness(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    _, lightness, _ = colorsys.rgb_to_hls(red, green, blue)
    return lightness
