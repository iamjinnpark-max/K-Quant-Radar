from dataclasses import asdict, dataclass

from fastapi import HTTPException

from .models import User


PAID_STATUSES = {"active", "trialing"}


@dataclass(frozen=True)
class Entitlements:
    manual_stock_limit: int
    max_scan_limit: int
    ai_recommendations: bool
    weekly_ai_recommendation_limit: int | None
    detailed_ai_reports: bool
    personalized_recommendations: bool
    unlimited_scans: bool
    ai_reports: bool
    portfolio_analysis: bool = False
    realtime_alerts: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


PLAN_ENTITLEMENTS = {
    "free": Entitlements(
        manual_stock_limit=5,
        max_scan_limit=5,
        ai_recommendations=False,
        weekly_ai_recommendation_limit=0,
        detailed_ai_reports=False,
        personalized_recommendations=False,
        unlimited_scans=False,
        ai_reports=False,
    ),
    "pro": Entitlements(
        manual_stock_limit=30,
        max_scan_limit=30,
        ai_recommendations=True,
        weekly_ai_recommendation_limit=5,
        detailed_ai_reports=False,
        personalized_recommendations=False,
        unlimited_scans=False,
        ai_reports=False,
    ),
    "premium": Entitlements(
        manual_stock_limit=60,
        max_scan_limit=60,
        ai_recommendations=True,
        weekly_ai_recommendation_limit=None,
        detailed_ai_reports=True,
        personalized_recommendations=True,
        unlimited_scans=True,
        ai_reports=True,
    ),
    "owner": Entitlements(
        manual_stock_limit=60,
        max_scan_limit=60,
        ai_recommendations=True,
        weekly_ai_recommendation_limit=None,
        detailed_ai_reports=True,
        personalized_recommendations=True,
        unlimited_scans=True,
        ai_reports=True,
    ),
}


def effective_plan(user: User) -> str:
    if user.is_owner:
        return "owner"
    if (
        user.subscription_status in PAID_STATUSES
        and user.plan in {"pro", "premium"}
    ):
        return user.plan
    return "free"


def entitlements_for(user: User) -> Entitlements:
    return PLAN_ENTITLEMENTS[effective_plan(user)]


def enforce_scan_limit(
    user: User,
    requested_limit: int,
    mode: str = "recommendations",
) -> Entitlements:
    entitlements = entitlements_for(user)
    plan = effective_plan(user)
    if mode == "recommendations" and not entitlements.ai_recommendations:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ai_recommendations_required",
                "plan": plan,
            },
        )

    limit = (
        entitlements.manual_stock_limit
        if mode == "manual"
        else entitlements.max_scan_limit
    )
    if requested_limit > limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "plan_limit",
                "plan": plan,
                "max_scan_limit": limit,
            },
        )
    return entitlements


def filter_recommendation_payload(user: User, payload: dict) -> dict:
    data = dict(payload)
    if not entitlements_for(user).detailed_ai_reports:
        data.pop("AI Analysis", None)
        data.pop("AI Analysis (KO)", None)
    return data
