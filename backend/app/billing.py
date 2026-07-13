import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select

from .audit import record_event
from .auth import get_current_user
from .config import get_settings
from .database import SessionLocal
from .models import User


router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def configured_settings(*, require_price=False, require_webhook=False):
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing is not configured")
    if require_price and not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Billing price is not configured")
    if require_webhook and not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured")
    stripe.api_key = settings.stripe_secret_key
    return settings


@router.post("/checkout")
def checkout(request: Request, user: User = Depends(get_current_user)):
    if user.is_owner:
        return {"url": get_settings().frontend_url}
    settings = configured_settings(require_price=True)

    customer = user.stripe_customer_id
    if not customer:
        created = stripe.Customer.create(
            email=user.email,
            metadata={"kquant_user_id": user.id},
        )
        customer = created.id
        with SessionLocal() as session:
            stored = session.get(User, user.id)
            stored.stripe_customer_id = customer
            session.commit()

    checkout_session = stripe.checkout.Session.create(
        customer=customer,
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/?billing=success",
        cancel_url=f"{settings.frontend_url}/?billing=cancelled",
        client_reference_id=user.id,
        allow_promotion_codes=True,
    )
    record_event(
        user_id=user.id,
        action="billing.checkout",
        resource_id=customer,
        request=request,
    )
    return {"url": checkout_session.url}


@router.post("/portal")
def portal(request: Request, user: User = Depends(get_current_user)):
    settings = configured_settings()
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=settings.frontend_url,
    )
    record_event(
        user_id=user.id,
        action="billing.portal",
        resource_id=user.stripe_customer_id,
        request=request,
    )
    return {"url": session.url}


@router.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request,
    stripe_signature: str | None = Header(
        default=None,
        alias="Stripe-Signature",
    ),
):
    settings = configured_settings(require_webhook=True)
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.stripe_webhook_secret,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid webhook") from error

    obj = event["data"]["object"]
    customer_id = obj.get("customer")
    if customer_id and event["type"].startswith("customer.subscription."):
        with SessionLocal() as session:
            user = session.scalar(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            if user:
                user.subscription_status = obj.get("status", "inactive")
                user.plan = "pro" if user.subscription_status in {
                    "active",
                    "trialing",
                } else "free"
                session.commit()
                record_event(
                    user_id=user.id,
                    action="billing.subscription_updated",
                    resource_id=customer_id,
                    detail=f"{event['type']} -> {user.subscription_status}",
                )
    return {"received": True}
