import pandas as pd
from pykrx import stock

FUNDAMENTAL_COLUMNS = ["bps", "per", "pbr", "eps", "div", "dps"]


def load_fundamentals(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Loads Korean valuation fundamentals (BPS, PER, PBR, EPS, DIV, DPS) as an
    actual daily point-in-time series, not a single snapshot broadcast across
    the whole window. PER/PBR move with price every trading day even between
    earnings reports, so pykrx's date-range endpoint gives real day-to-day
    variation instead of one constant value repeated for years of history.
    """
    try:
        result = stock.get_market_fundamental(start_date, end_date, ticker)
    except Exception as e:
        print(f"Fundamental time series failed for {ticker}: {e}")
        result = None

    if result is None or result.empty:
        print("No fundamental data found. Returning zeros.")
        result = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date))
        for col in FUNDAMENTAL_COLUMNS:
            result[col] = 0
        return result

    result = result.rename(
        columns={
            "BPS": "bps",
            "PER": "per",
            "PBR": "pbr",
            "EPS": "eps",
            "DIV": "div",
            "DPS": "dps",
        }
    )
    return result[FUNDAMENTAL_COLUMNS].fillna(0)


def add_fundamental_features(price_df: pd.DataFrame, fundamental_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()

    if fundamental_df is None or fundamental_df.empty:
        for col in FUNDAMENTAL_COLUMNS:
            df[col] = 0
    else:
        # Align by date rather than broadcasting one row -- forward-fill
        # covers weekends/holidays the fundamentals series may not include,
        # without ever pulling a future value backward in time.
        aligned = fundamental_df.reindex(df.index).ffill()
        for col in FUNDAMENTAL_COLUMNS:
            df[col] = aligned[col] if col in aligned.columns else 0

    df = df.fillna(0)

    df["eps_growth_20d"] = (
        df["eps"].pct_change(20).replace([float("inf"), float("-inf")], 0).fillna(0)
    )
    df["bps_growth_20d"] = (
        df["bps"].pct_change(20).replace([float("inf"), float("-inf")], 0).fillna(0)
    )

    df["value_score"] = 0

    df.loc[(df["per"] > 0) & (df["per"] < 15), "value_score"] += 1
    df.loc[(df["pbr"] > 0) & (df["pbr"] < 1.5), "value_score"] += 1
    df.loc[df["eps"] > 0, "value_score"] += 1
    df.loc[df["bps"] > 0, "value_score"] += 1

    return df