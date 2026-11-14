from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready", "env": get_settings().env}
