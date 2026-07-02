from datetime import datetime, timedelta
import pandas as pd
from pykrx import stock


def load_price_data(ticker: str, years: int = 3):
    end = datetime.today()
    start = end - timedelta(days=365 * years)

    df = stock.get_market_ohlcv_by_date(
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
        ticker
    )

    df = df.rename(columns={
        "시가": "open",
        "고가": "high",
        "저가": "low",
        "종가": "close",
        "거래량": "volume"
    })

    return df[["open", "high", "low", "close", "volume"]]


def get_company_name(ticker: str):
    try:
        return stock.get_market_ticker_name(ticker)
    except:
        return "Unknown Company"


def make_alpha_score(latest, probability):
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


def get_trade_action(score, probability, latest):
    if score["alpha_score"] >= 70:
        return "BUY", "Strong upside potential."

    elif score["alpha_score"] >= 45:
        return "HOLD", "Mixed signals."

    return "SELL", "Weak probability and momentum."