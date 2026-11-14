import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.pipeline.ingest.blocks import clean_text
from app.pipeline.ingest.jsonld import load_jsonld, node_types
from app.schemas.profile import Contact, Entities, Org, Person

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_NAME = re.compile(r"^[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){1,3}$")
_LOCATION = re.compile(
    r"(?:based in|located in|live in|from)\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+)?)",
)
_CITY_COUNTRY = re.compile(
    r"\b([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?),\s*([A-Z][a-zA-Z.'-]+)\b"
)
_STOP_COUNTRIES = {
    "Engineer",
    "Engineering",
    "Learning",
    "Science",
    "Design",
    "Development",
    "Portfolio",
    "Projects",
    "Project",
    "AI",
    "ML",
    "Data",
    "Software",
}
_SEPARATORS = ("|", "—", "–", " - ", "·", ":")


def _first(node: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return clean_text(value)
    return None


def _address_text(value: Any) -> str | None:
    if isinstance(value, str):
        return clean_text(value) if value.strip() else None
    if not isinstance(value, dict):
        return None
    locality = value.get("addressLocality")
    country = value.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = [str(part).strip() for part in (locality, country) if part]
    return ", ".join(parts) if parts else None


def _from_jsonld(nodes: list[dict[str, Any]]) -> Entities:
    person = Person()
    org = Org()
    contact = Contact()

    for node in nodes:
        types = node_types(node)
        if "Person" in types and person.name is None:
            person.name = _first(node, "name", "alternateName")
            person.role = _first(node, "jobTitle", "description")
            person.location = _address_text(node.get("address"))
            if contact.email is None:
                contact.email = _first(node, "email")
            if contact.url is None:
                contact.url = _first(node, "url", "sameAs")
        if {"Organization", "LocalBusiness", "Corporation"} & types and org.name is None:
            org.name = _first(node, "name", "legalName")
            if contact.email is None:
                contact.email = _first(node, "email")
            if person.location is None:
                person.location = _address_text(node.get("address"))

    return Entities(person=person, org=org, contact=contact)


def _title_parts(soup: BeautifulSoup) -> tuple[str, str | None]:
    title = clean_text(soup.title.get_text()) if soup.title else ""
    if not title:
        return "", None
    for separator in _SEPARATORS:
        if separator in title:
            left, right = title.split(separator, 1)
            left, right = clean_text(left), clean_text(right)
            if left and right:
                return left, right
    return title, None


def _header_name(soup: BeautifulSoup) -> str | None:
    heading = soup.find("h1")
    if heading is None:
        return None
    text = clean_text(heading.get_text())
    if len(text) <= 60 and _NAME.match(text):
        return text
    return None


def _subtitle(soup: BeautifulSoup) -> str | None:
    for node in soup.find_all(["p", "div", "span", "h2"]):
        marker = " ".join(
            [
                str(node.get("class") or ""),
                str(node.get("id") or ""),
            ]
        ).lower()
        if any(word in marker for word in ("role", "job-title", "subtitle", "tagline")):
            text = clean_text(node.get_text())
            if 2 <= len(text) <= 90:
                return text
    return None


def _find_location(text: str) -> str | None:
    match = _LOCATION.search(text)
    if match:
        return clean_text(match.group(1))
    for match in _CITY_COUNTRY.finditer(text):
        city, country = clean_text(match.group(1)), clean_text(match.group(2))
        if country in _STOP_COUNTRIES or city in _STOP_COUNTRIES:
            continue
        return f"{city}, {country}"
    return None


def _find_contact(soup: BeautifulSoup, base_url: str, text: str) -> Contact:
    emails: list[str] = []
    phones: list[str] = []
    contact_url: str | None = None

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href"))
        if href.startswith("mailto:"):
            candidate = href[7:].split("?")[0]
            if _EMAIL.fullmatch(candidate):
                emails.append(candidate)
        elif href.startswith("tel:"):
            phones.append(href[4:])
        else:
            label = clean_text(anchor.get_text()).lower()
            if contact_url is None and ("contact" in label or "contact" in href.lower()):
                contact_url = urljoin(base_url, href)

    emails.extend(_EMAIL.findall(text))
    phones.extend(_PHONE.findall(text))

    email = next((item for item in emails if not item.lower().endswith((".png", ".jpg"))), None)
    phone = None
    for candidate in phones:
        digits = re.sub(r"\D", "", candidate)
        if 8 <= len(digits) <= 15:
            phone = clean_text(candidate)
            break

    return Contact(email=email, phone=phone, url=contact_url)


def extract_entities(
    soup: BeautifulSoup,
    base_url: str,
    text: str,
) -> Entities:
    """Best-effort identity extraction from structured data and visible copy.

    Everything returned here is observed on the site. When a field cannot be
    established it stays ``None`` so the resolver can ask rather than invent.
    """
    entities = _from_jsonld(load_jsonld(soup))
    title_name, title_role = _title_parts(soup)
    site_name = next(
        (
            str(meta.get("content")).strip()
            for meta in soup.find_all("meta")
            if str(meta.get("property") or "").lower() == "og:site_name" and meta.get("content")
        ),
        None,
    )

    if entities.person.name is None:
        entities.person.name = _header_name(soup) or (
            title_name if _NAME.match(title_name) else None
        )
    if entities.person.role is None:
        role = _subtitle(soup)
        if role is None and title_role and title_role != site_name and len(title_role) <= 90:
            role = title_role
        entities.person.role = role
    if entities.person.location is None:
        entities.person.location = _find_location(text)
    if entities.org.name is None:
        entities.org.name = site_name
    if entities.org.name is None:
        match = re.search(r"©\s*\d{4}\s+([A-Z][\w&.' -]{2,60})", text)
        if match:
            entities.org.name = clean_text(match.group(1))

    contact = _find_contact(soup, base_url, text)
    if entities.contact.email is None:
        entities.contact.email = contact.email
    if entities.contact.phone is None:
        entities.contact.phone = contact.phone
    if entities.contact.url is None:
        entities.contact.url = contact.url
    if entities.contact.url:
        host = urlparse(entities.contact.url).netloc
        if not host:
            entities.contact.url = None

    return entities
