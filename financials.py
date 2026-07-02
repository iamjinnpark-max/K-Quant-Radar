import os
import pandas as pd
import OpenDartReader


def get_dart_api_key():
    api_key = os.getenv("DART_API_KEY")
    if api_key:
        return api_key

    try:
        import streamlit as st
        return st.secrets.get("DART_API_KEY")
    except (FileNotFoundError, KeyError, AttributeError):
        return None


def clean_number(value):
    if pd.isna(value):
        return 0
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return 0


def find_account(df, keywords):
    if df is None or df.empty:
        return 0

    for keyword in keywords:
        matched = df[
            df["account_nm"].astype(str).str.contains(keyword, case=False, na=False)
        ]

        if not matched.empty:
            return clean_number(matched.iloc[0].get("thstrm_amount", 0))

    return 0


def load_financials(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    api_key = get_dart_api_key()
    if not api_key:
        print(
            "DART_API_KEY is not configured; "
            f"skipping DART financials for {ticker}."
        )
        return pd.DataFrame()

    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
        print(
            f"DART initialization failed for {ticker}; "
            f"continuing without DART financials: {e}"
        )
        return pd.DataFrame()

    current_year = pd.Timestamp.today().year
    years = [current_year - 1, current_year - 2, current_year - 3]

    rows = []

    for year in years:
        try:
            fs = dart.finstate_all(ticker, year, reprt_code="11011")

            if fs is None or fs.empty:
                continue

            revenue = find_account(fs, ["매출액", "수익"])
            operating_profit = find_account(fs, ["영업이익"])
            net_income = find_account(fs, ["당기순이익"])
            total_liabilities = find_account(fs, ["부채총계"])
            total_equity = find_account(fs, ["자본총계"])
            cfo = find_account(fs, ["영업활동현금흐름"])
            capex = find_account(fs, ["유형자산의 취득", "유형자산 취득"])

            ebitda = operating_profit
            operating_margin = operating_profit / revenue if revenue else 0
            net_margin = net_income / revenue if revenue else 0
            roe = net_income / total_equity if total_equity else 0
            debt_ratio = total_liabilities / total_equity if total_equity else 0
            free_cash_flow = cfo - capex

            rows.append({
                "year": year,
                "revenue": revenue,
                "ebitda": ebitda,
                "net_income": net_income,
                "operating_margin": operating_margin,
                "net_margin": net_margin,
                "roe": roe,
                "debt_ratio": debt_ratio,
                "free_cash_flow": free_cash_flow,
            })

        except Exception as e:
            print(f"DART error for {ticker}, {year}: {e}")

    if not rows:
        return pd.DataFrame()

    latest = pd.DataFrame(rows).sort_values("year").iloc[-1].to_dict()

    result = pd.DataFrame(index=pd.date_range(start=start_date, end=end_date))

    for key, value in latest.items():
        if key != "year":
            result[key] = value

    return result


def add_financial_features(price_df: pd.DataFrame, financial_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()

    financial_cols = [
        "revenue",
        "ebitda",
        "net_income",
        "operating_margin",
        "net_margin",
        "roe",
        "debt_ratio",
        "free_cash_flow",
    ]

    if financial_df is None or financial_df.empty:
        for col in financial_cols:
            df[col] = 0
    else:
        latest_fundamentals = financial_df.iloc[-1]
        for col in financial_cols:
            df[col] = latest_fundamentals.get(col, 0)
        for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
            df[col] = latest_fundamentals.get(col, 0)

    df = df.fillna(0)

    df["financial_score"] = 0
    df.loc[df["revenue"] > 0, "financial_score"] += 1
    df.loc[df["ebitda"] > 0, "financial_score"] += 1
    df.loc[df["operating_margin"] > 0.10, "financial_score"] += 1
    df.loc[df["roe"] > 0.10, "financial_score"] += 1
    df.loc[df["debt_ratio"] < 2.0, "financial_score"] += 1
    df.loc[df["free_cash_flow"] > 0, "financial_score"] += 1

    return df
