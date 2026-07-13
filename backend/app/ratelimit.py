"""Per-client rate limiting backed by Redis.

The limiter intentionally does not trust claims from a bearer token before
authentication has verified its signature. In production the API is reachable
only through Caddy, which replaces untrusted X-Forwarded-For values.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler as rate_limit_exceeded_handler
from starlette.requests import Request

from .config import get_settings

__all__ = ["limiter", "rate_limit_key", "rate_limit_exceeded_handler"]


def rate_limit_key(request: Request) -> str:
    """Identify the network client without trusting attacker-controlled JWTs."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=get_settings().redis_url,
    default_limits=["120/minute"],
    headers_enabled=True,
)
