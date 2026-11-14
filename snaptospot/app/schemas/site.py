from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SiteCreate(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=300)


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    domain: str
    title: str | None
    status: str
    created_at: datetime
