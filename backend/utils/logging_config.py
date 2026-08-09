"""Structured JSON logging, with the request's identity attached.

Plain uvicorn access lines say a request happened. They do not say who made it,
which tenant it belonged to, or which of the day's log lines belong together —
which is exactly what you need at 2am, and exactly what you cannot add
retrospectively.

Every record carries `request_id`, `tenant`, `user` and `path` when they are
known, pulled from ContextVars set by the middleware. JSON because these are
read by a log processor far more often than by a person, and a person can still
read them.

Set ``LOG_FORMAT=text`` for human-friendly output during development.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Set per request by RequestContextMiddleware; read by the formatter.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_var: ContextVar[str] = ContextVar("log_user", default="")
tenant_var: ContextVar[str] = ContextVar("log_tenant", default="")
path_var: ContextVar[str] = ContextVar("log_path", default="")

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            # ISO-8601 UTC. Local time in logs is how two people compare
            # timestamps for an hour and reach different conclusions.
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, var in (
            ("request_id", request_id_var),
            ("tenant", tenant_var),
            ("user", user_var),
            ("path", path_var),
        ):
            value = var.get()
            if value:
                payload[key] = value

        # Anything passed via `extra=` rides along.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload.setdefault(key, value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get()
        who = user_var.get()
        prefix = " ".join(p for p in (rid[:8], who) if p)
        base = super().format(record)
        return f"{base}  [{prefix}]" if prefix else base


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if fmt == "json"
        else TextFormatter("%(levelname)s %(name)s: %(message)s")
    )

    root = logging.getLogger()
    # Replace rather than append: uvicorn installs its own handler, and adding
    # to it prints every line twice.
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
