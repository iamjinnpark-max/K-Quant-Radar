"""Append-only audit trail for trade-adjacent and access events.

Records who did what, when, and from where. Writes go to an isolated database
session and are committed independently of the request transaction, so an audit
entry survives even if the surrounding request later fails or rolls back. A
failure to write the audit row must never take down the user-facing request, so
all errors here are swallowed after best-effort logging.
"""
import logging

from starlette.requests import Request

from .database import SessionLocal
from .models import AuditLog

logger = logging.getLogger("kquant.audit")


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First hop is the original client; Caddy appends the proxy chain.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def record_event(
    _db=None,
    *,
    user_id: str | None,
    action: str,
    resource_id: str | None = None,
    request: Request | None = None,
    detail: str | None = None,
) -> None:
    """Persist a single audit event. Never raises.

    The leading positional argument is accepted and ignored so callers may pass
    their request-scoped session for readability; audit rows are always written
    on a dedicated session to keep the trail independent of request rollbacks.
    """
    try:
        with SessionLocal() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_id=resource_id,
                    client_ip=_client_ip(request),
                    detail=detail[:512] if detail else None,
                )
            )
            session.commit()
    except Exception:  # pragma: no cover - audit must not break requests
        logger.exception("Failed to write audit event action=%s", action)
