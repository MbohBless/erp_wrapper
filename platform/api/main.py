"""Control-plane FastAPI entrypoint.

Runs as its own service, with its own database and its own signing key. It is
never exposed on a tenant hostname — deploy it on an operator-only domain, and
keep ``/internal`` off the public proxy entirely.
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.audit import router as audit_router
from api.auth import operators as operators_router
from api.auth import router as auth_router
from api.health import router as health_router
from api.internal import router as internal_router
from api.plans import router as plans_router
from api.tenants import router as tenants_router
from config import settings
from database import Base, SessionLocal, engine
from models.audit import AuditLog  # noqa: F401 (register table)
from models.plan import DEFAULT_PLANS, Plan
from models.platform_user import PlatformRole, PlatformUser
from models.tenant import Tenant, TenantDomain  # noqa: F401 (register tables)
from repositories.plan_repository import PlanRepository
from repositories.platform_user_repository import PlatformUserRepository
from utils.security import hash_password

log = logging.getLogger("equimed.platform")


def _seed_plans() -> None:
    """Create the default plan catalogue so a fresh install is usable."""
    db = SessionLocal()
    try:
        repo = PlanRepository(db)
        for spec in DEFAULT_PLANS:
            if repo.get(spec["code"]) is not None:
                continue
            repo.add(
                Plan(
                    code=spec["code"],
                    name=spec["name"],
                    description=spec["description"],
                    features_json=json.dumps(spec["features"]),
                    max_users=spec["max_users"],
                    price_xaf=spec["price_xaf"],
                )
            )
    finally:
        db.close()


def _seed_owner() -> None:
    """Create the first platform owner if there is no way in yet."""
    if not settings.first_owner_email:
        return
    db = SessionLocal()
    try:
        repo = PlatformUserRepository(db)
        if repo.get_by_email(settings.first_owner_email) is None:
            repo.add(
                PlatformUser(
                    email=settings.first_owner_email,
                    full_name=settings.first_owner_name,
                    role=PlatformRole.OWNER.value,
                    is_active=True,
                    hashed_password=hash_password(settings.first_owner_password),
                )
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_plans()
    _seed_owner()
    # Surfaced at boot rather than buried in a doc: these are the settings that
    # quietly turn the platform into a liability if left at their defaults.
    for warning in settings.check_key_separation():
        log.warning("control-plane configuration: %s", warning)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        root_path=settings.root_path,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(auth_router)
    app.include_router(operators_router)
    app.include_router(tenants_router)
    app.include_router(plans_router)
    app.include_router(audit_router)
    return app


app = create_app()
