"""FastAPI application entrypoint.

Wires configuration, database, auth/RBAC and routers. Business logic lives in
the service layer — never in this file or the routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from middleware.observability import AuditMiddleware, RequestContextMiddleware
from utils.logging_config import configure_logging
from fastapi.responses import JSONResponse

from api.audit import router as audit_router
from api.auth import router as auth_router
from api.budget import router as budget_router
from api.internal import router as internal_router
from api.public import router as public_router
from api.reference import router as reference_router
from api.customers import router as customers_router
from api.dashboard import router as dashboard_router
from api.equipment import router as equipment_router
from api.finance import router as finance_router
from api.health import router as health_router
from api.inventory import router as inventory_router
from api.maintenance import router as maintenance_router
from api.payments import router as payments_router
from api.products import router as products_router
from api.purchases import router as purchases_router
from api.reports import router as reports_router
from api.sales import router as sales_router
from api.settings import router as settings_router
from api.setup import router as setup_router
from api.suppliers import router as suppliers_router
from api.users import router as users_router
from config import settings
from database import Base, SessionLocal, engine
from integrations.erpnext import ERPNextError
from models.audit import AuditEvent  # noqa: F401 (register table)
from models.books_setup import BooksSetup  # noqa: F401 (register table)
from models.branding import TenantBranding  # noqa: F401 (register table)
from models.budget import Budget  # noqa: F401 (register table)
from models.company_profile import CompanyProfile  # noqa: F401 (register table)
from models.refresh_token import RefreshToken  # noqa: F401 (register table)
from models.user import Role, User
from repositories.branding_repository import BrandingRepository
from repositories.company_repository import CompanyRepository
from repositories.user_repository import UserRepository
from tenancy import (
    DEFAULT_TENANT_ID,
    TenantMiddleware,
    TenantResolver,
    build_resolver,
)
from utils.security import hash_password


def _seed_administrator() -> None:
    """Create the initial Administrator account if it does not yet exist.

    Single-tenant only. On the SaaS plane each workspace's first administrator
    is created by the control plane through ``/internal/tenants/{id}/bootstrap``
    — an environment-seeded admin shared across tenants would be a back door.
    """
    if settings.tenancy_mode != "single" or not settings.first_admin_email:
        return
    db = SessionLocal()
    try:
        repo = UserRepository(db, settings.default_tenant_id)
        if repo.get_by_email(settings.first_admin_email) is None:
            repo.add(
                User(
                    email=settings.first_admin_email,
                    full_name=settings.first_admin_name,
                    role=Role.ADMINISTRATOR.value,
                    is_active=True,
                    hashed_password=hash_password(settings.first_admin_password),
                )
            )
    finally:
        db.close()


# Columns introduced after their table was first created. Still no Alembic:
# these are additive, defaulted and idempotent, which is exactly the shape
# ALTER TABLE ... ADD COLUMN handles safely on SQLite and MySQL alike.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "budget_line": {
        "months_json": "TEXT DEFAULT '[]'",
        "tenant_id": f"VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'",
    },
    "users": {"tenant_id": f"VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'"},
    "company_profile": {"tenant_id": f"VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'"},
    "books_setup": {"tenant_id": f"VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_TENANT_ID}'"},
}


def _ensure_columns() -> None:
    """Bring an existing database up to the current schema.

    Pre-multi-tenant rows land in the default tenant, which is what makes an
    in-place upgrade of a running single-tenant install a no-op for its users.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for table, cols in _ADDED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))

    if "users" in tables:
        _ensure_user_indexes()


def _ensure_user_indexes() -> None:
    """Move users from a globally-unique email to unique-per-tenant.

    The old ``ix_users_email`` unique index would stop two tenants from each
    having an ``admin@`` account, so it is replaced rather than supplemented.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("users")}

    with engine.begin() as conn:
        legacy = indexes.get("ix_users_email")
        if legacy is not None and legacy.get("unique"):
            conn.execute(text("DROP INDEX ix_users_email"))
            indexes.pop("ix_users_email")
        if "ix_users_email" not in indexes:
            conn.execute(text("CREATE INDEX ix_users_email ON users (email)"))
        if "ix_users_tenant_id" not in indexes:
            conn.execute(text("CREATE INDEX ix_users_tenant_id ON users (tenant_id)"))
        if "uq_users_tenant_email" not in indexes:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_users_tenant_email "
                    "ON users (tenant_id, email)"
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # V1 uses create_all (no migrations yet); introduce Alembic before schema
    # changes ship to production.
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _seed_administrator()
    # Materialise the default tenant's profile + branding rows so a fresh
    # single-tenant install renders before anyone opens Settings. On the SaaS
    # plane these are created per workspace at bootstrap instead.
    if settings.tenancy_mode == "single":
        db = SessionLocal()
        try:
            CompanyRepository(db, settings.default_tenant_id).get()
            BrandingRepository(db, settings.default_tenant_id).get()
        finally:
            db.close()
    yield


def create_app(resolver: TenantResolver | None = None) -> FastAPI:
    """Build the app. ``resolver`` is injectable so tests can drive the
    multi-tenant path without a live control plane."""
    # Before anything else, so startup itself is logged in the same shape as
    # everything after it.
    configure_logging(settings.log_level, settings.log_format)

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

    # Middleware order is the point here. add_middleware wraps outermost, so
    # the LAST call runs FIRST. The intended nesting is:
    #
    #   RequestContext  -> every request gets an id and log context, including
    #                      ones the tenant layer rejects
    #     Tenant        -> unknown/suspended workspaces rejected before auth
    #       Audit       -> needs current_tenant(), so it runs inside the binding
    #
    # which means registering them in exactly the reverse of that order.
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TenantMiddleware, resolver=resolver or build_resolver())
    app.add_middleware(RequestContextMiddleware)

    async def erpnext_error_handler(request: Request, exc: ERPNextError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.add_exception_handler(ERPNextError, erpnext_error_handler)

    app.include_router(audit_router)
    app.include_router(reference_router)
    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(public_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(suppliers_router)
    app.include_router(products_router)
    app.include_router(inventory_router)
    app.include_router(customers_router)
    app.include_router(sales_router)
    app.include_router(purchases_router)
    app.include_router(equipment_router)
    app.include_router(maintenance_router)
    app.include_router(finance_router)
    app.include_router(payments_router)
    app.include_router(dashboard_router)
    app.include_router(settings_router)
    app.include_router(reports_router)
    app.include_router(setup_router)
    app.include_router(budget_router)
    return app


app = create_app()
