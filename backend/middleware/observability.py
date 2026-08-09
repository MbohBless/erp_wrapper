"""Request identity, structured access logs, and the audit trail.

Two separate ASGI middlewares, because they need different positions relative to
the tenant binding:

    RequestContextMiddleware   outermost — every request gets an id and log
                               context, including ones the tenant layer rejects
    TenantMiddleware           (existing)
    AuditMiddleware            innermost — needs `current_tenant()`, so it must
                               run inside the tenant binding

Both are raw ASGI rather than ``BaseHTTPMiddleware`` for the same reason the
tenant middleware is: ``BaseHTTPMiddleware`` runs the downstream app in a child
task, and ContextVars set in one task are not reliably visible in another.
"""

from __future__ import annotations

import logging
import time
import uuid
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from utils.logging_config import (
    path_var,
    request_id_var,
    tenant_var,
    user_var,
)

log = logging.getLogger("equimed.request")
audit_log = logging.getLogger("equimed.audit")

# The actor is published by `get_current_user` into the ASGI scope under
# "audit_actor" — deliberately not a ContextVar. That dependency is a plain
# `def`, so FastAPI runs it in a threadpool, and a ContextVar set there is
# invisible to this middleware: the audit row records an empty actor and the
# whole point of the log is lost. The scope dict is shared for the request.

_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/static")
_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Path prefixes that are audited even on GET, because reading them is itself
# worth recording.
_AUDITED_READS = ("/audit",)


def _client_ip(scope: Scope) -> str:
    """The end user's address, not the proxy's.

    Caddy is configured to set X-Forwarded-For to the resolved client (see
    caddy/Caddyfile), so the first entry is the real one.
    """
    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    fwd = headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    client = scope.get("client")
    return (client[0] if client else "")[:64]


def _header(scope: Scope, name: str) -> str:
    for k, v in scope.get("headers", []):
        if k.decode().lower() == name:
            return v.decode()
    return ""


def describe(method: str, path: str) -> tuple[str, str, str]:
    """Turn a request into (action, resource_type, resource_id).

    `POST /users` -> ("user.create", "user", "")
    `PUT /customers/CHU%20X` -> ("customer.update", "customer", "CHU X")

    A stable verb is what makes the log searchable a year later; `method` and
    `path` are stored alongside for when the verb is not specific enough.
    """
    from urllib.parse import unquote

    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return ("http." + method.lower(), "", "")

    resource = parts[0].rstrip("s") if parts[0] != "auth" else "auth"
    verb = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
        "GET": "read",
    }.get(method, method.lower())

    # Sub-resource routes read better as their own verb: /auth/login ->
    # auth.login, /equipment/{id}/install -> equipment.install.
    tail = parts[-1]
    if len(parts) > 1 and not _looks_like_id(tail):
        return (f"{resource}.{tail}", resource, parts[1] if len(parts) > 2 else "")

    resource_id = unquote(tail) if len(parts) > 1 and _looks_like_id(tail) else ""
    return (f"{resource}.{verb}", resource, resource_id[:255])


def _looks_like_id(segment: str) -> bool:
    """Distinguish `/users/5` from `/auth/login`.

    Anything that is not a bare lowercase word is treated as an identifier —
    document names here look like `ACC-SINV-2026-00001` or `CHU Yaoundé`.
    """
    return not segment.isalpha() or not segment.islower()


class RequestContextMiddleware:
    """Assigns a request id and logs one structured line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Honour an inbound id so a trace can be followed across services;
        # generate one otherwise.
        rid = _header(scope, "x-request-id") or str(uuid.uuid4())
        path = scope.get("path", "")
        tokens = [
            request_id_var.set(rid),
            path_var.set(path),
            user_var.set(""),
            tenant_var.set(""),
        ]
        scope["request_id"] = rid

        status_holder: dict = {}
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                # Give the client the id so a user can quote it in a bug report.
                message.setdefault("headers", []).append(
                    (b"x-request-id", rid.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if not any(path.startswith(p) for p in _SKIP_PREFIXES):
                log.info(
                    "%s %s %s",
                    scope.get("method", ""),
                    path,
                    status_holder.get("status", 0),
                    extra={
                        "method": scope.get("method", ""),
                        "status": status_holder.get("status", 0),
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "ip": _client_ip(scope),
                        # Read from the scope for the same threadpool reason as
                        # the audit row.
                        "user": (scope.get("audit_actor") or {}).get("email", ""),
                    },
                )
            for tok, var in zip(
                tokens, (request_id_var, path_var, user_var, tenant_var)
            ):
                var.reset(tok)


class AuditMiddleware:
    """Writes an audit row for every state-changing request.

    Recording centrally rather than in each service is deliberate: a per-route
    call is one someone can forget to add, and the gap is invisible — an audit
    log's failure mode is silence. Every mutating request goes through here, so
    coverage is a property of the middleware rather than of everyone's memory.

    A failure to write the audit row does not fail the request. That is a real
    trade-off, taken knowingly: this system records commercial activity, and
    refusing a customer's invoice because a log row would not insert is the
    worse outcome. The failure is logged at ERROR so it is not silent.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        auditable = (
            method in _AUDITED_METHODS
            or any(path.startswith(p) for p in _AUDITED_READS)
        ) and not any(path.startswith(p) for p in _SKIP_PREFIXES)

        if not auditable:
            await self.app(scope, receive, send)
            return

        status_holder: dict = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            try:
                self._record(scope, method, path, status_holder.get("status", 0))
            except Exception:  # never fail the request over the audit trail
                audit_log.exception("failed to write audit event")

    def _record(self, scope: Scope, method: str, path: str, status: int) -> None:
        from database import SessionLocal
        from repositories.audit_repository import AuditRepository
        from tenancy.context import current_tenant

        actor = scope.get("audit_actor") or {}
        action, resource_type, resource_id = describe(method, path)

        # A fresh session: the request's own session is closed by now, and the
        # audit row must be committed even when the request itself rolled back.
        db = SessionLocal()
        try:
            AuditRepository(db, current_tenant().id).record(
                actor_id=actor.get("id"),
                actor_email=actor.get("email", "")[:255],
                actor_role=actor.get("role", "")[:50],
                action=action[:80],
                method=method[:10],
                path=path[:500],
                resource_type=resource_type[:80],
                resource_id=str(resource_id)[:255],
                status_code=status,
                succeeded=200 <= status < 400,
                ip_address=_client_ip(scope),
                user_agent=_header(scope, "user-agent")[:255],
                request_id=scope.get("request_id", "")[:36],
            )
        finally:
            db.close()
