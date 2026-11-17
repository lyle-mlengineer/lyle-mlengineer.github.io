from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Block(BaseModel):
    id: str
    kind: str
    text: str
    bbox: list[float] | None = None


class Heading(BaseModel):
    level: int
    text: str
    block_id: str | None = None


class Page(BaseModel):
    id: str
    url: str
    title: str
    headings: list[Heading] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)


class ColorToken(BaseModel):
    hex: str
    role: str = "unknown"
    area: float | None = None


class FontToken(BaseModel):
    family: str
    role: str = "unknown"


class LogoAsset(BaseModel):
    asset_id: str | None = None
    url: str | None = None
    transparent: bool | None = None


class Brand(BaseModel):
    colors: list[ColorToken] = Field(default_factory=list)
    fonts: list[FontToken] = Field(default_factory=list)
    logo: LogoAsset | None = None


class Person(BaseModel):
    name: str | None = None
    role: str | None = None
    location: str | None = None


class Org(BaseModel):
    name: str | None = None


class Contact(BaseModel):
    email: str | None = None
    phone: str | None = None
    url: str | None = None


class Entities(BaseModel):
    person: Person = Field(default_factory=Person)
    org: Org = Field(default_factory=Org)
    contact: Contact = Field(default_factory=Contact)


class ImageAsset(BaseModel):
    asset_id: str
    url: str
    role: str = "unknown"
    w: int | None = None
    h: int | None = None
    alt: str | None = None
    # Normalised [x, y, width, height] when a face or subject box is known.
    face_bbox: list[float] | None = None


class Observed(BaseModel):
    page_count: int
    asset_count: int
    crawled_at: datetime
    site_hash: str


class Gap(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    key: str
    gap_class: str = Field(alias="class")
    severity: str = "soft"
    reason: str = ""
    tried: list[str] = Field(default_factory=list)
    status: str = "open"
    resolved_by: str | None = None


class ValueProposition(BaseModel):
    text: str
    source_id: str | None = None


class PageRole(BaseModel):
    url: str
    role: str


class Offering(BaseModel):
    title: str
    summary: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class Understanding(BaseModel):
    """Machine reading of the site. Never a source of rendered facts by itself."""

    value_proposition: ValueProposition | None = None
    audience: str | None = None
    tone: list[str] = Field(default_factory=list)
    page_roles: list[PageRole] = Field(default_factory=list)
    offerings: list[Offering] = Field(default_factory=list)
    ai_generated: bool = False


class SiteProfile(BaseModel):
    url: str
    title: str
    pages: list[Page] = Field(default_factory=list)
    brand: Brand = Field(default_factory=Brand)
    entities: Entities = Field(default_factory=Entities)
    images: list[ImageAsset] = Field(default_factory=list)
    observed: Observed
    gaps: list[Gap] = Field(default_factory=list)
    understanding: Understanding = Field(default_factory=Understanding)
