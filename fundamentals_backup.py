import pandas as pd
from pykrx import stock


def load_fundamentals(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Loads Korean stock fundamental data.

    Common columns from pykrx:
    BPS, PER, PBR, EPS, DIV, DPS
    """

    df = stock.get_market_fundamental_by_date(
        start_date,
        end_date,
        ticker
    )

    print("Fundamental raw data:")
    print(df.tail())

    print("Fundamental columns:", df.columns)

    result = pd.DataFrame(index=df.index)

    for col in ["BPS", "PER", "PBR", "EPS", "DIV", "DPS"]:
        if col in df.columns:
            result[col.lower()] = df[col]
        else:
            result[col.lower()] = 0

    result = result.fillna(0)

    return result


def add_fundamental_features(price_df: pd.DataFrame, fundamental_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()
    df = df.join(fundamental_df, how="left")

    # Forward-fill missing fundamentals
    df = df.ffill()

    # Replace remaining missing values
    df = df.fillna(0)

    df["eps_growth_20d"] = df["eps"].pct_change(20).replace([float("inf"), -float("inf")], 0)
    df["bps_growth_20d"] = df["bps"].pct_change(20).replace([float("inf"), -float("inf")], 0)

    df["value_score"] = 0

    df.loc[(df["per"] > 0) & (df["per"] < 15), "value_score"] += 1
    df.loc[(df["pbr"] > 0) & (df["pbr"] < 1.5), "value_score"] += 1
    df.loc[df["eps_growth_20d"] > 0, "value_score"] += 1
    df.loc[df["bps_growth_20d"] > 0, "value_score"] += 1

    return df