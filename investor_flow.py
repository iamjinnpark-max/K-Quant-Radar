import pandas as pd
from pykrx import stock


def load_investor_flow(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = stock.get_market_trading_value_by_date(
        start_date,
        end_date,
        ticker
    )

    # Debug check
    print("Investor flow columns:", df.columns)

    # Create standardized columns safely
    result = pd.DataFrame(index=df.index)

    result["foreign_net_buy"] = 0
    result["institution_net_buy"] = 0
    result["individual_net_buy"] = 0

    if "외국인합계" in df.columns:
        result["foreign_net_buy"] = df["외국인합계"]
    elif "외국인" in df.columns:
        result["foreign_net_buy"] = df["외국인"]

    if "기관합계" in df.columns:
        result["institution_net_buy"] = df["기관합계"]
    elif "기관" in df.columns:
        result["institution_net_buy"] = df["기관"]

    if "개인" in df.columns:
        result["individual_net_buy"] = df["개인"]

    return result.fillna(0)


def add_investor_flow_features(price_df: pd.DataFrame, flow_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()
    df = df.join(flow_df, how="left")
    df = df.fillna(0)

    df["foreign_5d"] = df["foreign_net_buy"].rolling(5).sum()
    df["foreign_20d"] = df["foreign_net_buy"].rolling(20).sum()

    df["institution_5d"] = df["institution_net_buy"].rolling(5).sum()
    df["institution_20d"] = df["institution_net_buy"].rolling(20).sum()

    df["individual_5d"] = df["individual_net_buy"].rolling(5).sum()

    df["smart_money_5d"] = df["foreign_5d"] + df["institution_5d"]
    df["smart_money_20d"] = df["foreign_20d"] + df["institution_20d"]

    return df