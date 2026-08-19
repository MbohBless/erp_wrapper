# Coding Standards

Use FastAPI.

Use SQLAlchemy ORM.

Use Pydantic V2.

Never place business logic inside routers.

Use dependency injection.

All ERPNext communication must go through integrations/erpnext.py.

Outbound HTTP (httpx) is confined to `integrations/`. Today that is
`erpnext.py` and `control_plane.py` — everything that leaves the process over
the network is reviewable in one directory.

Use repository pattern.

Every app-owned table is tenant-scoped: add the `TenantScoped` mixin, and
construct its repository for one tenant so no query can be written unscoped.

Read the tenant through `tenancy.current_tenant()` only. Never read the
ContextVar directly — the single accessor is what makes isolation auditable.

Write unit tests. Tenant-scoped behaviour needs a cross-tenant test, not just a
happy-path one.

Generate OpenAPI automatically.

Return JSON API responses.
