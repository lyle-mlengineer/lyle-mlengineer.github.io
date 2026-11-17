from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.resolve import GapReport


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    site_id: str
    filename: str
    mime: str
    size_bytes: int
    sha256: str
    pages: int
    chunk_count: int
    fact_count: int
    status: str
    failure: str | None = None
    pinned_to_brand: bool = False
    expires_at: datetime | None = None
    created_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ordinal: int
    page: int
    kind: str
    tokens: int
    text: str


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut] = []


class DocumentReport(BaseModel):
    """The parse report returned for one uploaded file."""

    filename: str
    document_id: str | None = None
    status: str
    mime: str | None = None
    pages: int = 0
    chunks: int = 0
    extracted_facts: int = 0
    failures: list[str] = []


class UploadOut(BaseModel):
    run_id: str
    documents: list[DocumentReport] = []
    facts_extracted: int = 0
    gaps: GapReport


class PinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pinned: bool = True
