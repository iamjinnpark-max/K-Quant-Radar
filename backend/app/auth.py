from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient
from sqlalchemy import select
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


def decode_identity(authorization: str | None) -> Identity:
    settings = get_settings()
    if settings.auth_mode == "disabled":
        return Identity(
            sub="local-owner",
            email="owner@local.invalid",
            name="K-Quant Owner",
            groups=["owners"],
        )

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
        signing_key = PyJWKClient(
            f"{issuer}/.well-known/jwks.json",
            cache_keys=True,
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,
            issuer=issuer,
        )
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from error

    return Identity(
        sub=claims["sub"],
        email=claims.get("email"),
        name=claims.get("name") or claims.get("cognito:username"),
        groups=claims.get("cognito:groups", []),
    )


def get_current_user(
    authorization: str | None = Header(default=None),
) -> User:
    identity = decode_identity(authorization)
    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.cognito_sub == identity.sub)
        )
        if user is None:
            user = User(
                cognito_sub=identity.sub,
                email=identity.email,
                display_name=identity.name,
            )
            session.add(user)

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


def require_subscription(user: User = Depends(get_current_user)) -> User:
    if user.is_owner or user.subscription_status in {"active", "trialing"}:
        return user
    raise HTTPException(
        status_code=402,
        detail="An active subscription is required",
    )
