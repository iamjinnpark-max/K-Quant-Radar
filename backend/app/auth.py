from dataclasses import dataclass
from functools import lru_cache
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import unquote

import jwt
from fastapi import Header, HTTPException, Request
from jwt import PyJWKClient
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .models import User


@dataclass
class Identity:
    sub: str
    email: str | None
    name: str | None
    groups: list[str]


@lru_cache(maxsize=4)
def _jwk_client(issuer: str) -> PyJWKClient:
    """Reuse Cognito signing keys instead of fetching JWKS for every request."""
    return PyJWKClient(
        f"{issuer}/.well-known/jwks.json",
        cache_keys=True,
    )


@lru_cache(maxsize=4)
def _redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


def _unsign_cookie(value: str | None, secret: str | None) -> str | None:
    """Verify the cookie-signature format used by Express cookie-parser."""
    if not value or not secret:
        return None
    value = unquote(value)
    if not value.startswith("s:") or "." not in value:
        return None
    signed = value[2:]
    payload, supplied = signed.rsplit(".", 1)
    digest = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode().rstrip("=")
    if not hmac.compare_digest(supplied, expected):
        return None
    return payload


def _decode_session_identity(request: Request) -> Identity:
    settings = get_settings()
    sid = _unsign_cookie(
        request.cookies.get(settings.auth_session_cookie_name),
        settings.auth_cookie_secret,
    )
    if not sid or len(sid) > 128:
        raise HTTPException(status_code=401, detail="Authentication required")

    redis = _redis_client(settings.redis_url)
    raw = redis.get(f"auth:sess:{sid}")
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        record = json.loads(raw)
        auth_user_id = str(record["userId"])
        created_at = float(record["createdAt"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Invalid session") from error

    age_seconds = (time.time() * 1000 - created_at) / 1000
    remaining_absolute = settings.auth_session_absolute_ttl_seconds - age_seconds
    if remaining_absolute <= 0:
        redis.delete(f"auth:sess:{sid}")
        raise HTTPException(status_code=401, detail="Session expired")

    # Match the auth service's rolling idle window, but never let the Redis
    # TTL outlive the absolute cap measured from creation -- activity must
    # not extend a session past createdAt + absolute TTL.
    rolling_ttl = int(
        min(settings.auth_session_idle_ttl_seconds, remaining_absolute)
    )
    redis.expire(f"auth:sess:{sid}", max(rolling_ttl, 1))
    with SessionLocal() as session:
        row = session.execute(
            text(
                "SELECT email, email_verified_at "
                "FROM auth_users WHERE id = :id"
            ),
            {"id": auth_user_id},
        ).first()
    if row is None:
        redis.delete(f"auth:sess:{sid}")
        raise HTTPException(status_code=401, detail="Authentication required")
    if row.email_verified_at is None:
        # A session exists (so /auth/* flows work), but the private API stays
        # closed until the address is confirmed.
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_unverified",
                "message": "Verify your email address to use the API.",
            },
        )
    return Identity(
        sub=f"password:{auth_user_id}",
        email=row.email,
        name=row.email.split("@", 1)[0],
        groups=[],
    )


def decode_identity(
    authorization: str | None,
    request: Request | None = None,
) -> Identity:
    settings = get_settings()
    if settings.auth_mode == "disabled":
        return Identity(
            sub="local-owner",
            email="owner@local.invalid",
            name="K-Quant Owner",
            groups=["owners"],
        )
    if settings.auth_mode == "session":
        if request is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return _decode_session_identity(request)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    if not all(
        [
            settings.cognito_region,
            settings.cognito_user_pool_id,
            settings.cognito_app_client_id,
        ]
    ):
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    token = authorization.removeprefix("Bearer ").strip()
    issuer = (
        f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}"
    )
    try:
        signing_key = _jwk_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,
            issuer=issuer,
        )
        if claims.get("token_use") != "id":
            raise jwt.InvalidTokenError("Expected a Cognito ID token")
        groups = claims.get("cognito:groups", [])
        if not isinstance(groups, list) or not all(
            isinstance(group, str) for group in groups
        ):
            raise jwt.InvalidTokenError("Invalid Cognito groups claim")
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from error

    return Identity(
        sub=claims["sub"],
        email=claims.get("email"),
        name=claims.get("name") or claims.get("cognito:username"),
        groups=groups,
    )


def _select_user(session: Session, sub: str) -> User | None:
    return session.scalar(select(User).where(User.cognito_sub == sub))


def _sync_user(session: Session, identity: Identity) -> User:
    user = _select_user(session, identity.sub)
    if user is None:
        user = User(
            cognito_sub=identity.sub,
            email=identity.email,
            display_name=identity.name,
        )
        session.add(user)
        # Surface a duplicate-insert conflict here, inside the recoverable
        # scope, rather than at commit time.
        session.flush()

    user.email = identity.email or user.email
    user.display_name = identity.name or user.display_name
    user.is_owner = "owners" in identity.groups
    if user.is_owner:
        user.plan = "owner"
        user.subscription_status = "active"
    elif user.plan == "owner":
        # Removing a user from the Cognito owners group must revoke the
        # permanent bypass on their next authenticated request.
        user.plan = "free"
        user.subscription_status = "inactive"
    session.commit()
    session.refresh(user)
    session.expunge(user)
    return user


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> User:
    identity = decode_identity(authorization, request)
    with SessionLocal() as session:
        try:
            return _sync_user(session, identity)
        except IntegrityError:
            # Two first requests from the same new account can race the
            # SELECT-then-INSERT above. The unique constraint on cognito_sub
            # makes the loser fail its flush; recover by re-reading the row
            # the winner created instead of surfacing a 500.
            session.rollback()
            return _sync_user(session, identity)
