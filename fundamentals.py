import pandas as pd
from pykrx import stock


def load_fundamentals(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Loads latest Korean valuation fundamentals:
    BPS, PER, PBR, EPS, DIV, DPS
    """

    search_dates = [
        end_date,
        pd.Timestamp.today().strftime("%Y%m%d"),
        "20250630",
        "20241230",
        "20231228",
    ]

    for date in search_dates:
        try:
            snapshot = stock.get_market_fundamental(
                date,
                market="ALL"
            )

            if snapshot is not None and not snapshot.empty and ticker in snapshot.index:
                row = snapshot.loc[ticker]

                result = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date))

                result["bps"] = row.get("BPS", 0)
                result["per"] = row.get("PER", 0)
                result["pbr"] = row.get("PBR", 0)
                result["eps"] = row.get("EPS", 0)
                result["div"] = row.get("DIV", 0)
                result["dps"] = row.get("DPS", 0)

                print("Loaded fundamentals from:", date)
                print(row)

                return result.fillna(0)

        except Exception as e:
            print(f"Fundamental snapshot failed for {date}: {e}")

    print("No fundamental data found. Returning zeros.")

    result = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date))
    for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
        result[col] = 0

    return result


def add_fundamental_features(price_df: pd.DataFrame, fundamental_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()

    if fundamental_df is None or fundamental_df.empty:
        for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
            df[col] = 0
    else:
        latest_fundamentals = fundamental_df.iloc[-1]

        for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
            df[col] = latest_fundamentals.get(col, 0)

    df = df.fillna(0)

    df["eps_growth_20d"] = 0
    df["bps_growth_20d"] = 0

    df["value_score"] = 0

    df.loc[(df["per"] > 0) & (df["per"] < 15), "value_score"] += 1
    df.loc[(df["pbr"] > 0) & (df["pbr"] < 1.5), "value_score"] += 1
    df.loc[df["eps"] > 0, "value_score"] += 1
    df.loc[df["bps"] > 0, "value_score"] += 1

    return df