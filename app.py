from fundamentals import load_fundamentals, add_fundamental_features
from features import add_technical_features, add_prediction_target
from model import train_prediction_model, FEATURE_COLUMNS
from investor_flow import load_investor_flow, add_investor_flow_features
import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from pykrx import stock
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.ensemble import RandomForestClassifier

from financials import load_financials, add_financial_features

from news_sentiment import load_news_sentiment, add_news_features
from screener import run_screener, recommend_for_user
from personalization import calculate_personalized_score
from auth import require_access_password

st.set_page_config(
    page_title="K-Quant | Korean Market Intelligence",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    :root {
        --kq-ink: #132019;
        --kq-muted: #718078;
        --kq-green: #176a49;
        --kq-dark: #0d1d16;
        --kq-lime: #c9f56b;
        --kq-mint: #e1f4e9;
        --kq-line: #dfe6e1;
    }
    .stApp {
        background:
            radial-gradient(circle at 88% 2%, rgba(201,245,107,.15), transparent 25rem),
            #f2f5f2;
        color: var(--kq-ink);
    }
    .block-container {
        max-width: 1240px;
        padding-top: 2.2rem;
        padding-bottom: 5rem;
    }
    h1, h2, h3 {
        letter-spacing: -.035em;
    }
    .kq-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2rem;
    }
    .kq-brand {
        display: flex;
        align-items: center;
        gap: .75rem;
        font-size: 1.15rem;
        font-weight: 800;
    }
    .kq-logo {
        display: grid;
        place-items: center;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: .7rem;
        color: #172017;
        background: var(--kq-lime);
        box-shadow: 0 8px 22px rgba(201,245,107,.22);
    }
    .kq-live {
        padding: .55rem .8rem;
        border: 1px solid var(--kq-line);
        border-radius: 999px;
        background: white;
        color: var(--kq-muted);
        font-size: .68rem;
        font-weight: 800;
        letter-spacing: .08em;
    }
    .kq-live::before {
        content: "";
        display: inline-block;
        width: .45rem;
        height: .45rem;
        margin-right: .45rem;
        border-radius: 50%;
        background: #43bd78;
        box-shadow: 0 0 0 4px rgba(67,189,120,.12);
    }
    .hero-card {
        position: relative;
        overflow: hidden;
        min-height: 270px;
        padding: 3.2rem;
        border-radius: 1.5rem;
        color: white;
        background:
            linear-gradient(120deg, rgba(201,245,107,.08), transparent 55%),
            var(--kq-dark);
        box-shadow: 0 26px 70px rgba(17,45,31,.16);
        margin-bottom: 1.4rem;
    }
    .hero-card::after {
        content: "";
        position: absolute;
        width: 320px;
        height: 320px;
        right: -90px;
        top: -120px;
        border: 1px solid rgba(201,245,107,.28);
        border-radius: 50%;
        box-shadow:
            0 0 0 50px rgba(201,245,107,.035),
            0 0 0 100px rgba(201,245,107,.025);
    }
    .hero-card small {
        color: var(--kq-lime);
        font-size: .7rem;
        font-weight: 800;
        letter-spacing: .13em;
    }
    .hero-card h1 {
        max-width: 720px;
        margin: .8rem 0 1rem;
        font-size: clamp(2.6rem, 6vw, 5.2rem);
        line-height: .94;
        letter-spacing: -.065em;
    }
    .hero-card p {
        max-width: 620px;
        margin: 0;
        color: #aec0b7;
        line-height: 1.6;
    }
    .scan-heading {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 1rem;
        margin: 2.8rem 0 1rem;
    }
    .scan-heading span {
        display: inline-grid;
        place-items: center;
        width: 2rem;
        height: 2rem;
        margin-right: .6rem;
        border-radius: .6rem;
        background: var(--kq-mint);
        color: var(--kq-green);
        font-size: .72rem;
        font-weight: 800;
    }
    .scan-heading h2 {
        display: inline;
        margin: 0;
        font-size: 1.6rem;
    }
    .scan-heading p {
        margin: .35rem 0 0;
        color: var(--kq-muted);
        font-size: .85rem;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--kq-line);
        border-radius: 1.25rem;
        background: rgba(255,255,255,.94);
        box-shadow: 0 18px 55px rgba(22,48,35,.07);
    }
    div[data-baseweb="select"] > div,
    .stTextInput input {
        min-height: 2.8rem;
        border-color: var(--kq-line);
        border-radius: .7rem;
        background: #f8faf8;
    }
    .stButton > button {
        min-height: 2.9rem;
        border: 0;
        border-radius: .7rem;
        color: white;
        background: var(--kq-green);
        font-weight: 750;
        transition: all .16s ease;
    }
    .stButton > button:hover {
        color: white;
        border: 0;
        background: #0d422e;
        box-shadow: 0 10px 24px rgba(23,106,73,.2);
        transform: translateY(-1px);
    }
    div[data-testid="stMetric"] {
        padding: 1rem;
        border: 1px solid var(--kq-line);
        border-radius: .85rem;
        background: white;
    }
    .disclaimer {
        margin: 1rem 0;
        padding: .8rem 1rem;
        border-left: 3px solid var(--kq-green);
        border-radius: 0 .7rem .7rem 0;
        color: var(--kq-muted);
        background: rgba(255,255,255,.75);
        font-size: .78rem;
    }
    .ai-box {
        padding: 1.2rem 1.35rem;
        border-radius: 1rem;
        border: 1px solid #cce8d8;
        background: var(--kq-mint);
    }
    @media (max-width: 700px) {
        .block-container { padding: 1rem; }
        .hero-card { min-height: auto; padding: 2rem 1.4rem; }
        .hero-card h1 { font-size: 2.8rem; }
        .kq-live { display: none; }
    }
</style>
""", unsafe_allow_html=True)

require_access_password()

st.markdown("""
<div class="kq-nav">
    <div class="kq-brand"><span class="kq-logo">KQ</span>K-Quant</div>
    <div class="kq-live">KRX DATA LIVE</div>
</div>
<div class="hero-card">
    <small>KOREAN MARKET INTELLIGENCE · SEOUL</small>
    <h1>Find the signal.<br>Skip the noise.</h1>
    <p>
        Personalized KOSPI + KOSDAQ research powered by market structure,
        fundamentals, sentiment, and machine-learning probability.
    </p>
</div>
<div class="disclaimer">
    Research signal only—not financial advice. Model probabilities are not
    guaranteed outcomes.
</div>
<div class="scan-heading">
    <div>
        <span>01</span><h2>Build your scan</h2>
        <p>Shape the market around your risk, style, and favorite themes.</p>
    </div>
</div>
""", unsafe_allow_html=True)

with st.container(border=True):
    profile_col1, profile_col2, profile_col3, profile_col4 = st.columns(4)
    with profile_col1:
        market = st.selectbox(
            "Preferred Market",
            ["Korea", "US", "Global"],
        )
    with profile_col2:
        risk = st.selectbox(
            "Risk Level",
            ["Low", "Medium", "High"],
            index=1,
        )
    with profile_col3:
        style = st.selectbox(
            "Investment Style",
            ["Growth", "Value", "Dividend"],
        )
    with profile_col4:
        horizon = st.selectbox(
            "Time Horizon",
            [
                "0-3 Months",
                "3-6 Months",
                "6-12 Months",
                "1+ Years",
            ],
            index=1,
        )

    theme_col, size_col = st.columns([1.5, 1])
    with theme_col:
        favorite_sectors = st.multiselect(
            "Favorite Themes",
            [
                "AI",
                "Semiconductors",
                "EV",
                "Biotech",
                "Finance",
                "Internet",
                "Energy",
            ],
            default=["AI"],
        )
    with size_col:
        scan_limit = st.slider(
            "KRX scan size",
            min_value=10,
            max_value=60,
            value=30,
            step=10,
            help=(
                "Candidates are selected evenly from KOSPI and KOSDAQ, "
                "prioritizing your favorite sectors."
            ),
        )

user_profile = {
    "market": market,
    "risk_level": risk,
    "style": style,
    "time_horizon": horizon,
    "favorite_sectors": favorite_sectors,
    "scan_limit": scan_limit,
}


# -----------------------------
# Data
# -----------------------------
@st.cache_data(ttl=60 * 60)
def load_price_data(ticker: str, years: int = 3) -> pd.DataFrame:
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

    df = df[["open", "high", "low", "close", "volume"]]
    df = df.dropna()
    return df


@st.cache_data(ttl=60 * 60)
def get_company_name(ticker: str) -> str:
    try:
        return stock.get_market_ticker_name(ticker)
    except Exception:
        return "Unknown Company"


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["return_1d"] = df["close"].pct_change()
    df["return_5d"] = df["close"].pct_change(5)
    df["return_20d"] = df["close"].pct_change(20)

    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["volatility_20d"] = df["return_1d"].rolling(20).std()

    df["target"] = (df["close"].shift(-5) > df["close"]).astype(int)

    return df.dropna()


# -----------------------------
# Model
# -----------------------------
def train_model(df: pd.DataFrame):
    features = [
        "return_1d",
        "return_5d",
        "return_20d",
        "ma20",
        "ma60",
        "volume_ratio",
        "rsi",
        "volatility_20d"
    ]

    X = df[features]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, shuffle=False
    )

    model = RandomForestClassifier(
    n_estimators=120,
    max_depth=5,
    random_state=42
)

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds)

    latest_features = X.iloc[[-1]]
    bullish_probability = model.predict_proba(latest_features)[0][1]

    return model, accuracy, bullish_probability, features


# -----------------------------
# Scoring
# -----------------------------
def make_alpha_score(latest: pd.Series, probability: float) -> dict:
    momentum_score = 0

    if latest["close"] > latest["ma20"]:
        momentum_score += 15
    if latest["close"] > latest["ma60"]:
        momentum_score += 15
    if latest["return_20d"] > 0:
        momentum_score += 10

    volume_score = min(latest["volume_ratio"] / 2, 1) * 15

    rsi = latest["rsi"]
    if 45 <= rsi <= 65:
        rsi_score = 15
    elif 35 <= rsi < 45 or 65 < rsi <= 75:
        rsi_score = 10
    else:
        rsi_score = 5

    risk_penalty = min(latest["volatility_20d"] * 500, 20)

    model_score = probability * 40

    alpha_score = momentum_score + volume_score + rsi_score + model_score - risk_penalty
    alpha_score = max(0, min(100, alpha_score))

    if alpha_score >= 75:
        signal = "Bullish"
    elif alpha_score >= 55:
        signal = "Neutral-Bullish"
    elif alpha_score >= 40:
        signal = "Neutral"
    else:
        signal = "Weak"

    return {
        "alpha_score": round(alpha_score, 2),
        "signal": signal,
        "momentum_score": round(momentum_score, 2),
        "volume_score": round(volume_score, 2),
        "rsi_score": round(rsi_score, 2),
        "risk_penalty": round(risk_penalty, 2),
    }


def generate_explanation(latest: pd.Series, score: dict, probability: float) -> str:
    reasons = []

    if latest["close"] > latest["ma20"]:
        reasons.append("price is above the 20-day moving average")
    if latest["close"] > latest["ma60"]:
        reasons.append("price is above the 60-day moving average")
    if latest["volume_ratio"] > 1.5:
        reasons.append("volume is meaningfully above its 20-day average")
    if latest["rsi"] > 70:
        reasons.append("RSI is high, so short-term overheating risk exists")
    elif latest["rsi"] < 35:
        reasons.append("RSI is low, suggesting possible oversold conditions")
    if latest["adx_14"] >= 25:
        if latest["plus_di"] > latest["minus_di"]:
            reasons.append("ADX shows a strong bullish trend")
        else:
            reasons.append("ADX shows a strong bearish trend")
    elif latest["adx_14"] < 20:
        reasons.append("ADX suggests the stock may be moving sideways")
    if not reasons:
        reasons.append("the current signal is mixed without one dominant driver")

    return (
        f"The model estimates a 5-day bullish probability of "
        f"{probability:.1%}. The alpha score is {score['alpha_score']}/100. "
        f"The main drivers are: " + "; ".join(reasons) + "."
    )



def get_adx_signal(latest: pd.Series) -> str:
    adx = latest["adx_14"]
    plus_di = latest["plus_di"]
    minus_di = latest["minus_di"]

    if adx < 20:
        strength = "Weak / Choppy"
    elif adx < 25:
        strength = "Developing Trend"
    elif adx < 40:
        strength = "Strong Trend"
    else:
        strength = "Very Strong Trend"

    direction = "Bullish" if plus_di > minus_di else "Bearish"

    return f"{strength} ({direction})"
    
def get_trend_strength(latest):

    adx = latest["adx_14"]

    bullish = latest["plus_di"] > latest["minus_di"]

    if adx < 20:
        return "🟡 Sideways"

    elif adx < 25:
        return "🟢 Moderate Bullish" if bullish else "🔴 Moderate Bearish"

    elif adx < 40:
        return "🟢 Strong Bullish" if bullish else "🔴 Strong Bearish"

    else:
        return "🚀 Very Strong Bullish" if bullish else "📉 Very Strong Bearish"

def get_trade_action(score, probability, latest):
    alpha = score["alpha_score"]
    adx = latest["adx_14"]
    bullish_trend = latest["plus_di"] > latest["minus_di"]
    price_above_ma20 = latest["close"] > latest["ma20"]

    if alpha >= 70 and probability >= 0.60 and bullish_trend and price_above_ma20:
        return "BUY", "Strong score, bullish probability, and positive trend."

    elif alpha <= 40 or probability <= 0.40:
        return "SELL / AVOID", "Weak score or low bullish probability."

    else:
        return "HOLD / WATCH", "Mixed signal. Wait for stronger confirmation."

# -----------------------------
# UI
# -----------------------------
st.markdown("## Analyze one stock")
st.caption("Inspect probability, momentum, volume, RSI, trend, and risk in detail.")

ticker = st.text_input("Enter KRX ticker", value="005930")

if st.button("Analyze"):
    try:
        raw = load_price_data(ticker)
        company_name = get_company_name(ticker)
        st.subheader(f"{company_name} ({ticker})")
        news_data = load_news_sentiment(company_name)
        start_date = raw.index.min().strftime("%Y%m%d")
        end_date = raw.index.max().strftime("%Y%m%d")

        flow = load_investor_flow(ticker, start_date, end_date)
        fundamentals = load_fundamentals(ticker, start_date, end_date)
        financials = load_financials(ticker, start_date, end_date)
        df = raw.copy()
        df = add_news_features(df, news_data["news_score"])
        df = add_investor_flow_features(df, flow)
        print("After investor flow:", len(df))
        df = add_fundamental_features(df, fundamentals)
        df = add_financial_features(df, financials)
        print("After fundamentals:", len(df))
        df = add_technical_features(df)
        print("After technical:", len(df))
        df = add_prediction_target(df, days_ahead=5)
        print("Final dataset:", len(df))

        model, accuracy, probability = train_prediction_model(df)
        features = FEATURE_COLUMNS
        latest = df.iloc[-1]

        adx_signal = get_adx_signal(latest)
        trend_strength = get_trend_strength(latest)

        score = make_alpha_score(latest, probability)
        explanation = generate_explanation(latest, score, probability)
        trade_action, trade_reason = get_trade_action(score, probability, latest)

        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

        col1.metric("Signal", score["signal"])
        col2.metric("Alpha Score", score["alpha_score"])
        col3.metric("5-Day Bullish Probability", f"{probability:.1%}")
        col4.metric("Backtest Accuracy", f"{accuracy:.1%}")
        col5.metric("Trend Analysis", "🟢 Moderate Bullish")
        col6.metric("Action", trade_action)
        col7.metric("News Sentiment", f"{news_data['news_label']} ({news_data['news_score']:.2f})")
        st.caption(f"News Sentiment: {news_data['news_label']} | Score: {news_data['news_score']:.2f}")

        st.caption(f"Action reason: {trade_reason}")
        st.caption(f"ADX: {latest['adx_14']:.1f} | {adx_signal}")

        st.markdown(f"""
<div class="ai-box">
    <h3>🤖 AI Explanation</h3>
    <p>{explanation}</p>
</div>
""", unsafe_allow_html=True)
        st.write(explanation)
        chart_period = st.selectbox(
            "Chart period",
            ["3 Months", "6 Months", "1 Year", "Full History"],
            index=0
        )

        if chart_period == "3 Months":
            chart_df = df.tail(63)
        elif chart_period == "6 Months":
            chart_df = df.tail(126)
        elif chart_period == "1 Year":
            chart_df = df.tail(252)
        else:
            chart_df = df

        st.subheader("Price Chart")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x= chart_df.index,
            open=chart_df["open"],
            high=chart_df["high"],
            low=chart_df["low"],
            close=chart_df["close"],
            name="Price"
        ))

        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["ma20"],
            name="MA20"
        ))

        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["bb_upper"],
            name="Bollinger Upper"
        ))

        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["bb_lower"],
            name="Bollinger Lower"
        ))

        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["ma60"],
            name="MA60"
        ))

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Score Breakdown")
        st.dataframe(pd.DataFrame([score]))

        st.subheader("Latest Feature Data")
        st.dataframe(chart_df[features].tail(10))

        st.warning(
            "This is a research tool, not financial advice. "
            "The model estimates probabilities, not guaranteed outcomes."
        )

        st.divider()
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.write(traceback.format_exc())

st.subheader("Stock Ranking")
st.caption(
    "Leave the ticker field empty to scan personalized KOSPI + KOSDAQ "
    "candidates. Enter tickers only when you want a manual comparison."
)

ticker_input = st.text_input(
    "Optional tickers to rank",
    value="",
    placeholder="Example: 005930, 000660"
)

if st.button("Run Ranking"):
    ticker_list = [
        t.strip()
        for t in ticker_input.split(",")
        if t.strip()
    ]

    try:
        if ticker_list:
            ranking_df = run_screener(
                ticker_list,
                user_profile
            )
        else:
            ranking_df = recommend_for_user(user_profile)

        st.dataframe(ranking_df)
        market_counts = ranking_df["Market"].value_counts().to_dict()
        st.caption(
            f"Results: {len(ranking_df)} stocks | "
            f"KOSPI: {market_counts.get('KOSPI', 0)} | "
            f"KOSDAQ: {market_counts.get('KOSDAQ', 0)}"
        )

        st.subheader("Recommended Stocks")

        st.bar_chart(
            ranking_df.set_index("Company")[
                "Personalized Score"
            ]
        )

    except RuntimeError as e:
        st.error(str(e))

    st.divider()

st.subheader("AI Stock Recommendations")

st.caption(
    "K-Quant scans the market and suggests stocks based on your profile."
)

if st.button("Generate Recommendations"):

    try:
        recommendation_df = recommend_for_user(
            user_profile
        )

        st.dataframe(recommendation_df)
        market_counts = recommendation_df["Market"].value_counts().to_dict()
        st.caption(
            f"Results: {len(recommendation_df)} stocks | "
            f"KOSPI: {market_counts.get('KOSPI', 0)} | "
            f"KOSDAQ: {market_counts.get('KOSDAQ', 0)}"
        )

        st.subheader("Top Personalized Picks")

        st.bar_chart(
            recommendation_df.set_index("Company")[
                "Personalized Score"
            ]
        )

    except RuntimeError as e:
        st.error(str(e))


    
