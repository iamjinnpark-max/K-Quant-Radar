from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationProfile(BaseModel):
    mode: Literal["manual", "recommendations"] = "recommendations"
    market: Literal["Korea", "US", "Global"] = "Korea"
    risk_level: Literal["Low", "Medium", "High"] = "Medium"
    style: Literal["Growth", "Value", "Dividend"] = "Growth"
    time_horizon: Literal[
        "0-3 Months",
        "3-6 Months",
        "6-12 Months",
        "1+ Years",
    ] = "3-6 Months"
    favorite_sectors: list[
        Literal[
            "AI",
            "Semiconductors",
            "EV",
            "Biotech",
            "Finance",
            "Internet",
            "Energy",
        ]
    ] = Field(default_factory=list, max_length=7)
    scan_limit: int = Field(default=5, ge=1, le=60)
    manual_tickers: list[str] = Field(default_factory=list, max_length=60)


class JobCreated(BaseModel):
    id: str
    status: str


class RecommendationResult(BaseModel):
    rank: int
    ticker: str
    company: str
    data: dict


class JobResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    recommendations: list[RecommendationResult]
