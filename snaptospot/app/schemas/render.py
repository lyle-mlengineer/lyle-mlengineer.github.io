from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design import CardId


class RenderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platforms: list[str] = Field(default_factory=lambda: ["linkedin"], max_length=8)
    cards: list[CardId] = Field(
        default_factory=lambda: ["hero", "capabilities", "projects", "proof"],
        max_length=4,
    )
    reuse_cache: bool = True


class RenderedAssetOut(BaseModel):
    asset: str
    filename: str
    path: str
    width: int
    height: int
    sha256: str
    size: int
    cache_key: str
    cached: bool
    template_version: str


class RenderOut(BaseModel):
    run_id: str
    content_model_hash: str
    design_system_hash: str
    renderer_version: str
    platform: str
    assets: list[RenderedAssetOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rendered_at: date
