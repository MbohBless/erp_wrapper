"""Liveness endpoint (unauthenticated)."""

from fastapi import APIRouter

from config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "provisioner": settings.provisioner,
    }
