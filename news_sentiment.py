import feedparser
import pandas as pd
from urllib.parse import quote


POSITIVE_KEYWORDS = [
    "beat", "surge", "growth", "record", "profit", "upgrade", "strong",
    "호실적", "상승", "성장", "최대", "수혜", "개선", "증가", "강세"
]

NEGATIVE_KEYWORDS = [
    "miss", "fall", "drop", "loss", "downgrade", "weak", "decline",
    "부진", "하락", "감소", "적자", "약세", "악화", "우려", "손실"
]


def score_headline(text: str) -> int:
    text_lower = text.lower()

    positive_hits = sum(1 for word in POSITIVE_KEYWORDS if word.lower() in text_lower)
    negative_hits = sum(1 for word in NEGATIVE_KEYWORDS if word.lower() in text_lower)

    if positive_hits > negative_hits:
        return 1
    elif negative_hits > positive_hits:
        return -1
    else:
        return 0


def load_news_sentiment(company_name: str, max_articles: int = 10) -> dict:
    query = quote(company_name)
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=ko&gl=KR&ceid=KR:ko"

    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries[:max_articles]:
        title = entry.get("title", "")
        score = score_headline(title)

        articles.append({
            "title": title,
            "sentiment_score": score
        })

    if not articles:
        return {
            "news_score": 0,
            "news_label": "Neutral",
            "articles": []
        }

    df = pd.DataFrame(articles)
    avg_score = df["sentiment_score"].mean()

    if avg_score > 0.2:
        label = "Positive"
    elif avg_score < -0.2:
        label = "Negative"
    else:
        label = "Neutral"

    return {
        "news_score": avg_score,
        "news_label": label,
        "articles": articles
    }


def add_news_features(df: pd.DataFrame, news_score: float) -> pd.DataFrame:
    df = df.copy()
    df["news_score"] = news_score
    return df