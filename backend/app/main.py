from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .auth import get_current_user, require_subscription
from .billing import router as billing_router
from .database import SessionLocal
from .models import RecommendationJob, User
from .schemas import (
    JobCreated,
    JobResult,
    RecommendationProfile,
    RecommendationResult,
)
from .tasks import run_recommendation_job


settings = get_settings()
app = FastAPI(
    title="K-Quant API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(billing_router)


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
        "plan": user.plan,
        "subscription_status": user.subscription_status,
    }


@app.post(
    "/api/v1/recommendation-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_job(
    profile: RecommendationProfile,
    db: Session = Depends(get_db),
    user: User = Depends(require_subscription),
):
    job = RecommendationJob(
        profile=profile.model_dump(),
        user_id=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    run_recommendation_job.delay(job.id)
    return JobCreated(id=job.id, status=job.status)


@app.get(
    "/api/v1/recommendation-jobs/{job_id}",
    response_model=JobResult,
)
def get_job(
    job_id: str,
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
        raise HTTPException(status_code=404, detail="Job not found")

    recommendations = [
        RecommendationResult(
            rank=item.rank,
            ticker=item.ticker,
            company=item.company,
            data=item.payload,
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
