from datetime import datetime, timedelta, timezone
import hmac

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from .audit import record_event
from .config import get_settings
from .auth import _unsign_cookie, get_current_user
from .billing import router as billing_router
from .database import SessionLocal
from .entitlements import (
    effective_plan,
    enforce_scan_limit,
    entitlements_for,
    filter_recommendation_payload,
)
from .models import RecommendationJob, User
from .ratelimit import limiter, rate_limit_exceeded_handler
from .schemas import (
    JobCreated,
    JobResult,
    RecommendationProfile,
    RecommendationResult,
)
from .tasks import run_recommendation_job
from stock_universe import FALLBACK_UNIVERSE, get_full_market_universe


settings = get_settings()
app = FastAPI(
    title="K-Quant API",
    version="1.0.0",
    docs_url="/api/docs" if settings.api_docs_enabled else None,
    openapi_url="/api/openapi.json" if settings.api_docs_enabled else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)
app.include_router(billing_router)


@app.middleware("http")
async def enforce_csrf_for_cookie_auth(request: Request, call_next):
    """Reject cross-site state changes when the API uses auth cookies."""
    if (
        settings.auth_mode == "session"
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and request.url.path != "/api/v1/billing/webhook"
    ):
        cookie_token = _unsign_cookie(
            request.cookies.get(settings.auth_csrf_cookie_name),
            settings.auth_cookie_secret,
        )
        header_token = request.headers.get(settings.auth_csrf_header_name)
        if not cookie_token or not header_token or not hmac.compare_digest(
            cookie_token, header_token
        ):
            return Response(
                content='{"detail":"Invalid CSRF token"}',
                status_code=403,
                media_type="application/json",
            )
    return await call_next(request)


def get_db():
    with SessionLocal() as session:
        yield session


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/v1/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_owner": user.is_owner,
        "plan": effective_plan(user),
        "subscription_status": user.subscription_status,
        "entitlements": entitlements_for(user).as_dict(),
    }


def _normalize_tickers(values: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for value in values:
        ticker = str(value).strip()
        if ticker.endswith(".0"):
            ticker = ticker[:-2]
        if not ticker:
            continue
        ticker = ticker.zfill(6)
        if not ticker.isdigit() or len(ticker) != 6:
            raise HTTPException(
                status_code=422,
                detail="manual_tickers must be six-digit Korean stock codes.",
            )
        if ticker not in seen:
            seen.add(ticker)
            normalized.append(ticker)
    return normalized


def _weekly_recommendation_usage(db: Session, user: User) -> int:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return db.scalar(
        select(func.count(RecommendationJob.id)).where(
            RecommendationJob.user_id == user.id,
            RecommendationJob.created_at >= week_ago,
            RecommendationJob.profile["mode"].as_string() == "recommendations",
            RecommendationJob.status != "failed",
        )
    ) or 0


@app.get("/api/v1/stocks/search")
def search_stocks(
    q: str = Query("", max_length=80),
    limit: int = Query(10, ge=1, le=25),
    user: User = Depends(get_current_user),
):
    query = q.strip().lower()
    try:
        universe = get_full_market_universe()
    except Exception:
        import pandas as pd
        universe = pd.DataFrame(FALLBACK_UNIVERSE)
    if universe.empty:
        return []

    searchable = universe.copy()
    searchable["ticker"] = searchable["ticker"].astype(str).str.zfill(6)
    searchable = searchable[searchable["ticker"].str.fullmatch(r"\d{6}")]
    searchable["company"] = searchable["company"].fillna("").astype(str)
    if query:
        searchable = searchable[
            searchable["ticker"].str.contains(query, regex=False)
            | searchable["company"].str.lower().str.contains(query, regex=False)
        ]
    return searchable.head(limit)[
        ["ticker", "company", "exchange", "sector"]
    ].to_dict("records")


@app.post(
    "/api/v1/recommendation-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
def create_job(
    request: Request,
    response: Response,
    profile: RecommendationProfile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mode = profile.mode
    job_profile = profile.model_dump()
    if mode == "manual":
        tickers = _normalize_tickers(profile.manual_tickers)
        if not tickers:
            raise HTTPException(
                status_code=422,
                detail="Choose at least one stock for manual analysis.",
            )
        entitlements = enforce_scan_limit(user, len(tickers), mode=mode)
        job_profile["manual_tickers"] = tickers
        job_profile["scan_limit"] = len(tickers)
    else:
        entitlements = enforce_scan_limit(user, profile.scan_limit, mode=mode)
        weekly_limit = entitlements.weekly_ai_recommendation_limit
        if weekly_limit is not None:
            used = _weekly_recommendation_usage(db, user)
            if used >= weekly_limit:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "weekly_ai_recommendation_limit",
                        "plan": effective_plan(user),
                        "weekly_limit": weekly_limit,
                        "used": used,
                    },
                )
            job_profile["weekly_recommendation_usage"] = {
                "used": used + 1,
                "limit": weekly_limit,
            }
    job_profile["personalized"] = (
        entitlements.personalized_recommendations
    )
    if not entitlements.personalized_recommendations:
        job_profile["favorite_sectors"] = []
    job = RecommendationJob(
        profile=job_profile,
        user_id=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    record_event(
        db,
        user_id=user.id,
        action="recommendation_job.create",
        resource_id=job.id,
        request=request,
    )
    run_recommendation_job.delay(job.id)
    return JobCreated(id=job.id, status=job.status)


@app.get(
    "/api/v1/recommendation-jobs/{job_id}",
    response_model=JobResult,
)
def get_job(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.scalar(
        select(RecommendationJob)
        .where(
            RecommendationJob.id == job_id,
            RecommendationJob.user_id == user.id,
        )
        .options(selectinload(RecommendationJob.recommendations))
    )
    if job is None:
        record_event(
            db,
            user_id=user.id,
            action="recommendation_job.access_denied",
            resource_id=job_id,
            request=request,
        )
        raise HTTPException(status_code=404, detail="Job not found")

    record_event(
        db,
        user_id=user.id,
        action="recommendation_job.view",
        resource_id=job.id,
        request=request,
    )
    recommendations = [
        RecommendationResult(
            rank=item.rank,
            ticker=item.ticker,
            company=item.company,
            data=filter_recommendation_payload(user, item.payload),
        )
        for item in job.recommendations
    ]
    return JobResult(
        id=job.id,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        recommendations=recommendations,
    )
