"""FastAPI application entrypoint.

Wires configuration, database, auth/RBAC and routers. Business logic lives in
the service layer — never in this file or the routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import router as auth_router
from api.budget import router as budget_router
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
from models.books_setup import BooksSetup  # noqa: F401 (register table)
from models.budget import Budget  # noqa: F401 (register table)
from models.company_profile import CompanyProfile  # noqa: F401 (register table)
from models.user import Role, User
from repositories.company_repository import CompanyRepository
from repositories.user_repository import UserRepository
from utils.security import hash_password


def _seed_administrator() -> None:
    """Create the initial Administrator account if it does not yet exist."""
    if not settings.first_admin_email:
        return
    db = SessionLocal()
    try:
        repo = UserRepository(db)
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


def _ensure_columns() -> None:
    """Add columns introduced after a table was created (no Alembic yet)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    adds = {"budget_line": {"months_json": "TEXT DEFAULT '[]'"}}
    for table, cols in adds.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # V1 uses create_all (no migrations yet); introduce Alembic before schema
    # changes ship to production.
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _seed_administrator()
    # Ensure the singleton branding profile exists (defaults to EquiMed).
    db = SessionLocal()
    try:
        CompanyRepository(db).get()
    finally:
        db.close()
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

    async def erpnext_error_handler(request: Request, exc: ERPNextError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.add_exception_handler(ERPNextError, erpnext_error_handler)

    app.include_router(health_router)
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
