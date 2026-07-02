import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from screener import recommend_for_user

from .celery_app import celery_app
from .database import SessionLocal
from .models import Recommendation, RecommendationJob


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


@celery_app.task(name="run_recommendation_job")
def run_recommendation_job(job_id: str):
    with SessionLocal() as session:
        job = session.get(RecommendationJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()
        profile = job.profile

    try:
        dataframe = recommend_for_user(profile)
        rows = [
            json_safe(record)
            for record in dataframe.reset_index(drop=True).to_dict("records")
        ]

        with SessionLocal() as session:
            job = session.get(RecommendationJob, job_id)
            for rank, row in enumerate(rows, start=1):
                session.add(
                    Recommendation(
                        job_id=job_id,
                        rank=rank,
                        ticker=str(row.get("Ticker", "")),
                        company=str(row.get("Company", "")),
                        payload=row,
                    )
                )
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as error:
        with SessionLocal() as session:
            job = session.get(RecommendationJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = f"{type(error).__name__}: {error}"[:2000]
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
        raise
