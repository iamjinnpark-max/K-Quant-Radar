import pandas as pd


from features import add_technical_features, add_prediction_target
from investor_flow import load_investor_flow, add_investor_flow_features
from fundamentals import load_fundamentals, add_fundamental_features
from financials import load_financials, add_financial_features
from news_sentiment import load_news_sentiment, add_news_features
from model import train_prediction_model
from utils import (
    load_price_data,
    get_company_name
)
from personalization import calculate_personalized_score
from pykrx import stock
from stock_universe import (
    get_full_market_universe,
    select_personalized_candidates,
)
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

    df = add_technical_features(df)
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
    candidates = select_personalized_candidates(
        universe_df,
        user_profile,
        limit=scan_limit,
    )

    tickers = candidates["ticker"].tolist()
    stock_metadata = {
        row["ticker"]: row
        for row in candidates.to_dict("records")
    }

    recommendation_df = run_screener(
        tickers,
        user_profile,
        stock_metadata=stock_metadata,
    )

    return recommendation_df

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
