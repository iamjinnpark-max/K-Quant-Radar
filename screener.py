import pandas as pd
from datetime import datetime, timezone
from urllib.parse import quote


from features import add_technical_features, add_prediction_target
from investor_flow import load_investor_flow, add_investor_flow_features
from fundamentals import load_fundamentals, add_fundamental_features
from financials import load_financials, add_financial_features
from news_sentiment import load_news_sentiment, add_news_features
from regime import add_regime_features
from options_signals import KrxIndexOptionsDataSource, add_options_features
from model import train_prediction_model
from utils import (
    load_price_data,
    get_company_name
)
from personalization import calculate_personalized_score
from pykrx import stock
from stock_universe import (
    FALLBACK_UNIVERSE,
    get_full_market_universe,
    select_personalized_candidates,
)
# Shared across every ticker in a run: KOSPI200 options data currently has no
# live vendor wired in, so this always reports itself unavailable and the
# resulting iv_skew_25d/gex_proxy features stay neutral (see options_signals.py).
_OPTIONS_DATA_SOURCE = KrxIndexOptionsDataSource()


# --------------------------------------------------
# Alpha Score
# --------------------------------------------------
def make_alpha_score(probability: float) -> dict:

    alpha_score = round(probability * 100, 2)

    if alpha_score >= 70:
        signal = "Strong Buy"
    elif alpha_score >= 55:
        signal = "Buy"
    elif alpha_score >= 45:
        signal = "Hold"
    else:
        signal = "Sell"

    return {
        "alpha_score": alpha_score,
        "signal": signal
    }


# --------------------------------------------------
# Trading Action
# --------------------------------------------------
def get_trade_action(score: dict):

    signal = score["signal"]

    if signal == "Strong Buy":
        return "BUY", "High upside probability"

    elif signal == "Buy":
        return "ACCUMULATE", "Moderate upside probability"

    elif signal == "Hold":
        return "HOLD", "Mixed signals"

    else:
        return "SELL", "Weak probability outlook"


# --------------------------------------------------
# Single Stock Analysis
# --------------------------------------------------
def _calculate_momentum_score(latest: pd.Series) -> float:
    momentum_score = 50
    momentum_score += 15 if latest["close"] > latest["ma20"] else -10
    momentum_score += 15 if latest["close"] > latest["ma60"] else -10
    momentum_score += 10 if latest["return_20d"] > 0 else -10
    momentum_score += 10 if latest["return_5d"] > 0 else -5
    return round(max(0, min(100, momentum_score)), 2)


def _infer_stock_profile(
    latest: pd.Series,
    stock_meta: dict,
) -> dict:
    daily_volatility = float(latest.get("volatility_20d", 0))
    if daily_volatility < 0.015:
        risk = "Low"
    elif daily_volatility < 0.03:
        risk = "Medium"
    else:
        risk = "High"

    dividend_yield = float(latest.get("div", 0))
    per = float(latest.get("per", 0))
    pbr = float(latest.get("pbr", 0))

    if dividend_yield >= 2:
        style = "Dividend"
    elif (0 < per < 15) or (0 < pbr < 1.5):
        style = "Value"
    else:
        style = "Growth"

    adx = float(latest.get("adx_14", 0))
    if risk == "High":
        time_horizon = "0-3 Months"
    elif risk == "Low":
        time_horizon = "1+ Years"
    elif adx >= 25:
        time_horizon = "3-6 Months"
    else:
        time_horizon = "6-12 Months"

    return {
        "market": "Korea",
        "exchange": stock_meta.get("exchange", "KRX"),
        "sector": stock_meta.get("sector", ""),
        "risk": risk,
        "style": style,
        "time_horizon": time_horizon,
        "tags": stock_meta.get("tags", []),
    }


def _generate_stock_analysis(
    score: dict,
    probability: float,
    accuracy: float,
    latest: pd.Series,
    stock_profile: dict,
    momentum_score: float,
) -> str:
    trend = (
        "above"
        if latest["close"] > latest["ma20"]
        else "below"
    )
    direction = (
        "bullish"
        if latest["plus_di"] > latest["minus_di"]
        else "bearish"
    )
    return (
        f"The model assigns a {probability:.1%} five-day bullish probability "
        f"with {accuracy:.1%} holdout accuracy. The stock is trading {trend} "
        f"its 20-day average, while ADX direction is {direction}. "
        f"Momentum scores {momentum_score:.0f}/100 and the observed volatility "
        f"maps to {stock_profile['risk'].lower()} risk. The resulting "
        f"{score['signal'].lower()} signal should be treated as a ranked "
        f"research signal, not a forecast or guarantee."
    )


def _generate_stock_analysis_ko(
    score: dict,
    probability: float,
    accuracy: float,
    latest: pd.Series,
    stock_profile: dict,
    momentum_score: float,
) -> str:
    trend = "상회" if latest["close"] > latest["ma20"] else "하회"
    direction = (
        "상승 우위"
        if latest["plus_di"] > latest["minus_di"]
        else "하락 우위"
    )
    risk = {
        "Low": "낮은",
        "Medium": "중간",
        "High": "높은",
    }.get(stock_profile["risk"], stock_profile["risk"])
    signal = {
        "Strong Buy": "강력 매수",
        "Buy": "매수",
        "Hold": "보유",
        "Sell": "매도",
    }.get(score["signal"], score["signal"])
    return (
        f"모델의 5거래일 상승 확률은 {probability:.1%}, 검증 구간 정확도는 "
        f"{accuracy:.1%}입니다. 현재 주가는 20일 이동평균을 {trend}하고 있으며, "
        f"ADX 방향성은 {direction}입니다. 모멘텀 점수는 "
        f"{momentum_score:.0f}/100이고 관측 변동성 기준 위험도는 {risk} 수준입니다. "
        f"종합 신호는 {signal}이지만, 이는 순위형 리서치 신호이며 수익을 "
        f"보장하는 예측이 아닙니다."
    )


def _build_price_chart(df: pd.DataFrame, limit: int = 126) -> list[dict]:
    """Serialize a compact six-month technical series for the web chart."""
    columns = [
        "close",
        "ma20",
        "ma60",
        "bb_upper",
        "bb_lower",
    ]
    chart_df = df.tail(limit)
    points = []
    for index, row in chart_df.iterrows():
        point = {"date": pd.Timestamp(index).strftime("%Y-%m-%d")}
        for column in columns:
            value = row.get(column)
            point[column] = (
                round(float(value), 2)
                if value is not None and pd.notna(value)
                else None
            )
        points.append(point)
    return points


def _build_analysis_sources(
    ticker: str,
    company_name: str,
    start_date: str,
    end_date: str,
    news_data: dict,
    financials: pd.DataFrame,
) -> list[dict]:
    """Describe the upstream information used to build a stock analysis."""
    accessed_at = datetime.now(timezone.utc).isoformat()
    krx_url = "https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd"
    sources = [
        {
            "name": "KRX market data",
            "name_ko": "KRX 시장 데이터",
            "provider": "Korea Exchange",
            "provider_ko": "한국거래소",
            "category": "Price, valuation, and investor flow",
            "category_ko": "가격·밸류에이션·수급",
            "url": krx_url,
            "description": (
                "Historical OHLCV, valuation fundamentals, and investor trading "
                "flows used by the model."
            ),
            "description_ko": (
                "모델에 사용된 과거 시세, 밸류에이션 지표, 투자자별 거래 흐름입니다."
            ),
            "as_of": end_date,
            "period_start": start_date,
            "accessed_at": accessed_at,
        },
    ]

    if financials is not None and not financials.empty:
        sources.append({
            "name": "Corporate financial statements",
            "name_ko": "기업 재무제표",
            "provider": "Open DART",
            "provider_ko": "전자공시시스템 Open DART",
            "category": "Regulatory filings",
            "category_ko": "공시 재무정보",
            "url": (
                "https://dart.fss.or.kr/dsab007/main.do"
                f"?option=corp&keyword={quote(ticker)}"
            ),
            "description": (
                "Annual financial statements used for profitability, leverage, "
                "and cash-flow features."
            ),
            "description_ko": (
                "수익성, 부채 수준, 현금흐름 분석에 사용된 연간 재무제표입니다."
            ),
            "as_of": end_date,
            "accessed_at": accessed_at,
        })

    feed_url = news_data.get("feed_url")
    if feed_url:
        sources.append({
            "name": f"{company_name} news search",
            "name_ko": f"{company_name} 뉴스 검색",
            "provider": "Google News",
            "provider_ko": "Google 뉴스",
            "category": "News sentiment",
            "category_ko": "뉴스 심리",
            "url": feed_url,
            "description": (
                "RSS headlines scored for the news-sentiment feature. "
                "Individual articles used are listed below."
            ),
            "description_ko": (
                "뉴스 심리 점수에 반영된 RSS 헤드라인입니다. 사용된 개별 기사는 "
                "아래에서 확인할 수 있습니다."
            ),
            "accessed_at": accessed_at,
        })

    for article in news_data.get("articles", []):
        if not article.get("url"):
            continue
        sources.append({
            "name": article.get("title") or "News article",
            "provider": article.get("publisher") or "News publisher",
            "category": "News article",
            "category_ko": "뉴스 기사",
            "url": article["url"],
            "description": "Headline included in the news-sentiment score.",
            "description_ko": "뉴스 심리 점수에 반영된 헤드라인입니다.",
            "published_at": article.get("published_at") or None,
            "accessed_at": accessed_at,
        })

    return sources


def analyze_one_stock(ticker: str, stock_meta=None):

    stock_meta = stock_meta or SECTOR_DB.get(ticker, {})
    raw = load_price_data(ticker)

    if raw is None or raw.empty:
        raise ValueError(f"No price history returned for {ticker}.")

    start_date = raw.index.min().strftime("%Y%m%d")
    end_date = raw.index.max().strftime("%Y%m%d")

    company_name = stock_meta.get("company") or get_company_name(ticker)

    # Load data sources
    flow = load_investor_flow(ticker, start_date, end_date)
    fundamentals = load_fundamentals(
        ticker,
        start_date,
        end_date
    )

    financials = load_financials(
        ticker,
        start_date,
        end_date
    )
    news_data = load_news_sentiment(company_name)

    # Feature engineering
    df = add_investor_flow_features(raw, flow)
    df = add_fundamental_features(df, fundamentals)
    df = add_financial_features(df, financials)
    df = add_news_features(df, news_data["news_score"])
    df = add_regime_features(df)
    df = add_options_features(df, _OPTIONS_DATA_SOURCE)

    df = add_technical_features(df)
    chart_data = _build_price_chart(df)
    df = add_prediction_target(df)

    if df.empty:
        raise ValueError(
            f"Feature engineering produced no training rows for {ticker}."
        )

    latest = df.iloc[-1]
    stock_profile = _infer_stock_profile(latest, stock_meta)
    momentum_score = _calculate_momentum_score(latest)

    # Train model
    model, accuracy, probability = train_prediction_model(df)

    # Final scoring
    score = make_alpha_score(probability)
    action, reason = get_trade_action(score)

    return {
    "Ticker": ticker,
    "Company": company_name,
    "Alpha Score": score["alpha_score"],
    "Bullish Probability (%)": round(probability * 100, 2),
    "Signal": score["signal"],
    "Action": action,
    "News": news_data["news_label"],
    "Model Accuracy (%)": round(accuracy * 100, 2),
    "Reason": reason,
    "AI Analysis": _generate_stock_analysis(
        score,
        probability,
        accuracy,
        latest,
        stock_profile,
        momentum_score,
    ),
    "AI Analysis (KO)": _generate_stock_analysis_ko(
        score,
        probability,
        accuracy,
        latest,
        stock_profile,
        momentum_score,
    ),
    "Sources": _build_analysis_sources(
        ticker,
        company_name,
        start_date,
        end_date,
        news_data,
        financials,
    ),
    "Chart Data": chart_data,

    "Market": stock_profile["exchange"],
    "Sector": stock_profile["sector"],
    "Risk": stock_profile["risk"],
    "Style": stock_profile["style"],
    "Time Horizon": stock_profile["time_horizon"],
    "market": stock_profile["market"],
    "risk": stock_profile["risk"],
    "style": stock_profile["style"],
    "time_horizon": stock_profile["time_horizon"],
    "tags": stock_profile["tags"],
    "momentum_score": momentum_score,
}


# --------------------------------------------------
# Multi-Stock Screener
# --------------------------------------------------
def run_screener(tickers, user_profile=None, stock_metadata=None):
    results = []
    failures = []
    stock_metadata = stock_metadata or {}

    for ticker in tickers:
        try:
            print(f"Analyzing {ticker}...")
            result = analyze_one_stock(
                ticker,
                stock_metadata.get(ticker),
            )
            if user_profile is not None:
                result["Personalized Score"] = calculate_personalized_score(
                    user_profile,
                    {
                        "alpha_score": result["Alpha Score"],
                        "momentum_score": result["momentum_score"],
                        "market": result["market"],
                        "risk": result["risk"],
                        "style": result["style"],
                        "time_horizon": result["time_horizon"],
                        "tags": result["tags"],
                    }
                )
            else:
                result["Personalized Score"] = result["Alpha Score"]

            results.append(result)

        except Exception as e:
            import traceback
            error = f"{ticker}: {type(e).__name__}: {e}"
            failures.append(error)
            print(f"\nFAILED {error}")
            print(traceback.format_exc())

    if len(results) == 0:
        failure_details = " | ".join(failures) or "No tickers were supplied."
        raise RuntimeError(
            f"Every stock analysis failed. {failure_details}"
        )

    ranking_df = pd.DataFrame(results)

    ranking_df = ranking_df.sort_values(
        by="Personalized Score",
        ascending=False
    )

    ranking_df.reset_index(drop=True, inplace=True)
    ranking_df.index += 1

    return ranking_df

from pykrx import stock





def recommend_for_user(user_profile):

    universe_df = get_full_market_universe()

    if universe_df.empty:
        raise RuntimeError("The stock universe is empty.")

    if "ticker" not in universe_df.columns:
        raise RuntimeError(
            f"The stock universe has no ticker column. "
            f"Columns: {list(universe_df.columns)}"
        )

    scan_limit = user_profile.get("scan_limit", 30)
    personalized = bool(user_profile.get("personalized", False))
    candidates = select_personalized_candidates(
        universe_df,
        user_profile if personalized else {"favorite_sectors": []},
        limit=scan_limit,
    )

    tickers = candidates["ticker"].tolist()
    stock_metadata = {
        row["ticker"]: row
        for row in candidates.to_dict("records")
    }

    recommendation_df = run_screener(
        tickers,
        user_profile if personalized else None,
        stock_metadata=stock_metadata,
    )

    return recommendation_df


def analyze_selected_stocks(tickers, user_profile=None):
    try:
        universe_df = get_full_market_universe()
    except Exception:
        universe_df = pd.DataFrame(FALLBACK_UNIVERSE)
    normalized = []
    seen = set()
    for ticker in tickers:
        value = str(ticker).strip()
        if not value:
            continue
        value = value[:-2] if value.endswith(".0") else value
        value = value.zfill(6)
        if value not in seen:
            seen.add(value)
            normalized.append(value)

    if not normalized:
        raise RuntimeError("No tickers were supplied for manual analysis.")

    stock_metadata = {}
    if not universe_df.empty and "ticker" in universe_df.columns:
        matching = universe_df[universe_df["ticker"].isin(normalized)]
        stock_metadata = {
            row["ticker"]: row
            for row in matching.to_dict("records")
        }

    return run_screener(
        normalized,
        user_profile,
        stock_metadata=stock_metadata,
    )

def get_market_universe(market="KOSPI", limit=30):
    from datetime import datetime, timedelta
    from pykrx import stock

    today = datetime.today()

    for i in range(10):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y%m%d")

        try:
            ohlcv = stock.get_market_ohlcv_by_ticker(
                date_str,
                market=market
            )

            if ohlcv is not None and not ohlcv.empty:
                ohlcv = ohlcv.sort_values("거래대금", ascending=False)
                tickers = list(ohlcv.head(limit).index)

                print(f"Loaded {len(tickers)} active tickers from {date_str}")
                return tickers

        except Exception as e:
            print(f"Market universe failed for {date_str}: {e}")

    return []

SECTOR_DB = {
    "005930": {
        "market": "Korea",
        "risk": "Medium",
        "style": "Growth",
        "time_horizon": "3-6 Months",
        "tags": ["AI", "Semiconductors"]
    },

    "000660": {
        "market": "Korea",
        "risk": "High",
        "style": "Growth",
        "time_horizon": "3-6 Months",
        "tags": ["AI", "Semiconductors"]
    },

    "035420": {
        "market": "Korea",
        "risk": "Medium",
        "style": "Growth",
        "time_horizon": "6-12 Months",
        "tags": ["Internet", "AI"]
    }
}
