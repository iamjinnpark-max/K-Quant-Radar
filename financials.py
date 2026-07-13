import os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

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


FINANCIAL_COLUMNS = [
    "revenue",
    "ebitda",
    "net_income",
    "operating_margin",
    "net_margin",
    "roe",
    "debt_ratio",
    "free_cash_flow",
]

# Korean annual business reports (사업보고서) are due within 90 days of
# fiscal year-end (Dec 31), so a report for fiscal year Y is treated as
# becoming known starting April 1 of Y+1 -- a conservative approximation
# (the exact filing date is available from DART's `rcept_no` but isn't
# fetched here) that avoids ever applying a report's numbers to dates
# before it was actually public.
_ANNUAL_REPORT_EFFECTIVE_MONTH = 4
_ANNUAL_REPORT_EFFECTIVE_DAY = 1


def load_financials(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    api_key = get_dart_api_key()
    if not api_key:
        print(
            "DART_API_KEY is not configured; "
            f"skipping DART financials for {ticker}."
        )
        return pd.DataFrame()

    try:
        import OpenDartReader
        dart = OpenDartReader(api_key)
    except Exception as e:
        print(
            f"DART initialization failed for {ticker}; "
            f"continuing without DART financials: {e}"
        )
        return pd.DataFrame()

    end_year = pd.Timestamp(end_date).year
    # A handful of years back so the point-in-time series has coverage
    # across most of a multi-year training window, not just its tail end.
    years = range(end_year - 4, end_year + 1)

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

            effective_date = pd.Timestamp(
                year=year + 1,
                month=_ANNUAL_REPORT_EFFECTIVE_MONTH,
                day=_ANNUAL_REPORT_EFFECTIVE_DAY,
            )

            rows.append({
                "effective_date": effective_date,
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

    snapshots = (
        pd.DataFrame(rows)
        .sort_values("effective_date")
        .set_index("effective_date")
    )

    full_index = pd.date_range(start=start_date, end=end_date)
    # Forward-fill each report's numbers from its effective date onward;
    # dates before the earliest effective report stay NaN (zero-filled by
    # add_financial_features), never pulling a later report's data backward.
    combined_index = snapshots.index.union(full_index)
    result = snapshots.reindex(combined_index).sort_index().ffill()
    return result.reindex(full_index)


def add_financial_features(price_df: pd.DataFrame, financial_df: pd.DataFrame) -> pd.DataFrame:
    df = price_df.copy()

    if financial_df is None or financial_df.empty:
        for col in FINANCIAL_COLUMNS:
            df[col] = 0
    else:
        aligned = financial_df.reindex(df.index).ffill()
        for col in FINANCIAL_COLUMNS:
            df[col] = aligned[col] if col in aligned.columns else 0

    df = df.fillna(0)

    df["financial_score"] = 0
    df.loc[df["revenue"] > 0, "financial_score"] += 1
    df.loc[df["ebitda"] > 0, "financial_score"] += 1
    df.loc[df["operating_margin"] > 0.10, "financial_score"] += 1
    df.loc[df["roe"] > 0.10, "financial_score"] += 1
    df.loc[df["debt_ratio"] < 2.0, "financial_score"] += 1
    df.loc[df["free_cash_flow"] > 0, "financial_score"] += 1

    return df
