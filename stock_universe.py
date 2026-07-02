from datetime import datetime, timedelta
from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from pykrx import stock


KIND_MARKETS = {
    "KOSPI": "stockMkt",
    "KOSDAQ": "kosdaqMkt",
}

SECTOR_KEYWORDS = {
    "AI": ["ai", "인공지능", "머신러닝", "소프트웨어", "데이터"],
    "Semiconductors": ["반도체", "semiconductor", "웨이퍼", "집적회로"],
    "EV": ["전기차", "이차전지", "2차전지", "배터리", "자동차부품"],
    "Biotech": ["바이오", "제약", "의약", "의료", "신약"],
    "Finance": ["금융", "은행", "증권", "보험", "카드"],
    "Internet": ["인터넷", "플랫폼", "포털", "온라인", "정보서비스"],
    "Energy": ["에너지", "전력", "가스", "석유", "태양광", "풍력", "수소"],
}

FALLBACK_UNIVERSE = [
    {
        "ticker": "005930",
        "company": "삼성전자",
        "exchange": "KOSPI",
        "sector": "통신 및 방송 장비 제조업",
        "products": "반도체, 전자제품",
    },
    {
        "ticker": "000660",
        "company": "SK하이닉스",
        "exchange": "KOSPI",
        "sector": "반도체 제조업",
        "products": "메모리 반도체",
    },
    {
        "ticker": "035420",
        "company": "NAVER",
        "exchange": "KOSPI",
        "sector": "자료처리 및 인터넷 정보매개 서비스업",
        "products": "인터넷 플랫폼, 인공지능",
    },
    {
        "ticker": "051910",
        "company": "LG화학",
        "exchange": "KOSPI",
        "sector": "기초 화학물질 제조업",
        "products": "석유화학, 배터리 소재",
    },
    {
        "ticker": "373220",
        "company": "LG에너지솔루션",
        "exchange": "KOSPI",
        "sector": "일차전지 및 축전지 제조업",
        "products": "전기차 배터리",
    },
]


def _normalize_ticker(value) -> str:
    ticker = str(value).strip()
    if ticker.endswith(".0"):
        ticker = ticker[:-2]
    return ticker.zfill(6)


def _infer_tags(sector: str, products: str) -> list:
    description = f"{sector} {products}".lower()
    return [
        tag
        for tag, keywords in SECTOR_KEYWORDS.items()
        if any(keyword.lower() in description for keyword in keywords)
    ]


def _load_kind_market(exchange: str, market_type: str) -> pd.DataFrame:
    url = (
        "https://kind.krx.co.kr/corpgeneral/corpList.do"
        f"?method=download&searchType=13&marketType={market_type}"
    )
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    html = response.content.decode("euc-kr", errors="replace")
    tables = pd.read_html(StringIO(html), flavor="lxml")

    if not tables:
        raise RuntimeError(f"KRX KIND returned no table for {exchange}.")

    source = tables[0]
    required_columns = {"회사명", "종목코드", "업종", "주요제품"}
    missing_columns = required_columns.difference(source.columns)
    if missing_columns:
        raise RuntimeError(
            f"KRX KIND {exchange} response is missing columns: "
            f"{sorted(missing_columns)}"
        )

    result = source[
        ["회사명", "종목코드", "업종", "주요제품"]
    ].rename(
        columns={
            "회사명": "company",
            "종목코드": "ticker",
            "업종": "sector",
            "주요제품": "products",
        }
    )
    result["ticker"] = result["ticker"].map(_normalize_ticker)
    result["exchange"] = exchange
    result["sector"] = result["sector"].fillna("").astype(str)
    result["products"] = result["products"].fillna("").astype(str)
    result["tags"] = result.apply(
        lambda row: _infer_tags(row["sector"], row["products"]),
        axis=1,
    )
    return result[
        ["ticker", "company", "exchange", "sector", "products", "tags"]
    ]


def _load_pykrx_universe() -> pd.DataFrame:
    today = datetime.today()

    for i in range(10):
        date = (today - timedelta(days=i)).strftime("%Y%m%d")
        rows = []

        try:
            for exchange in ("KOSPI", "KOSDAQ"):
                tickers = stock.get_market_ticker_list(
                    date=date,
                    market=exchange,
                )
                for ticker in tickers:
                    rows.append(
                        {
                            "ticker": ticker,
                            "company": stock.get_market_ticker_name(ticker),
                            "exchange": exchange,
                            "sector": "",
                            "products": "",
                            "tags": [],
                        }
                    )

            if rows:
                print(f"Loaded {len(rows)} stocks from pykrx for {date}")
                return pd.DataFrame(rows)

            print(f"No pykrx tickers returned for {date}")
        except Exception as e:
            print(f"pykrx universe failed for {date}: {e}")

    return pd.DataFrame()


@lru_cache(maxsize=1)
def _cached_full_market_universe() -> pd.DataFrame:
    try:
        markets = [
            _load_kind_market(exchange, market_type)
            for exchange, market_type in KIND_MARKETS.items()
        ]
        universe = pd.concat(markets, ignore_index=True)
        universe = universe.drop_duplicates(subset="ticker", keep="first")
        print(
            "Loaded KRX universe: "
            f"{(universe['exchange'] == 'KOSPI').sum()} KOSPI + "
            f"{(universe['exchange'] == 'KOSDAQ').sum()} KOSDAQ"
        )
        return universe
    except Exception as e:
        print(f"KRX KIND universe failed: {e}")

    universe = _load_pykrx_universe()
    if not universe.empty:
        return universe

    raise RuntimeError(
        "Unable to load the KOSPI/KOSDAQ universe from KRX KIND or pykrx. "
        "Full-market recommendations were not generated."
    )


def get_full_market_universe() -> pd.DataFrame:
    return _cached_full_market_universe().copy(deep=True)


def select_personalized_candidates(
    universe_df: pd.DataFrame,
    user_profile: dict,
    limit: int = 30,
) -> pd.DataFrame:
    if universe_df.empty:
        return universe_df.copy()

    candidates = universe_df.copy()
    favorite_sectors = set(user_profile.get("favorite_sectors", []))

    candidates["interest_matches"] = candidates["tags"].map(
        lambda tags: len(favorite_sectors.intersection(tags))
    )
    candidates["has_profile_match"] = (
        candidates["interest_matches"] > 0
    ).astype(int)
    candidates = candidates.sort_values(
        ["has_profile_match", "interest_matches", "company"],
        ascending=[False, False, True],
    )

    limit = max(2, min(int(limit), len(candidates)))
    kospi_limit = (limit + 1) // 2
    kosdaq_limit = limit // 2

    kospi = candidates[candidates["exchange"] == "KOSPI"].head(kospi_limit)
    kosdaq = candidates[candidates["exchange"] == "KOSDAQ"].head(kosdaq_limit)

    # Interleave both markets so neither exchange is postponed to the end.
    rows = []
    for index in range(max(len(kospi), len(kosdaq))):
        if index < len(kospi):
            rows.append(kospi.iloc[index])
        if index < len(kosdaq):
            rows.append(kosdaq.iloc[index])

    selected = pd.DataFrame(rows).reset_index(drop=True)
    return selected.drop(
        columns=["interest_matches", "has_profile_match"],
        errors="ignore",
    )
