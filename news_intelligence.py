from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

import feedparser
import requests

from config import ENABLE_NEWS
from api_manager import get_api_settings


log = logging.getLogger("news-intelligence")

NEWSAPI_URL = "https://newsapi.org/v2/everything"

POSITIVE = {
    "beat",
    "growth",
    "surge",
    "rally",
    "gain",
    "record",
    "approval",
    "partnership",
    "profit",
    "upgrade",
    "bullish",
    "strong",
    "breakthrough",
    "outperform",
    "expansion",
    "rebound",
    "soar",
}

NEGATIVE = {
    "miss",
    "loss",
    "fall",
    "drop",
    "lawsuit",
    "probe",
    "fraud",
    "downgrade",
    "bearish",
    "weak",
    "risk",
    "ban",
    "hack",
    "recession",
    "warning",
    "decline",
    "slump",
    "cut",
    "investigation",
}


@dataclass
class NewsResult:
    sentiment: float
    headlines: list[str]
    source: str
    message: str = ""


def _score(text: str) -> float:
    words = set(
        re.findall(
            r"[a-zA-Z]+",
            str(text).lower(),
        )
    )

    positive_count = len(words & POSITIVE)
    negative_count = len(words & NEGATIVE)
    total = positive_count + negative_count

    if total == 0:
        return 0.0

    return (
        positive_count - negative_count
    ) / total


def _average_sentiment(
    headlines: list[str],
) -> float:
    if not headlines:
        return 0.0

    return sum(
        _score(headline)
        for headline in headlines
    ) / len(headlines)


def _get_newsapi_key() -> str:
    # First check Railway environment variables directly.
    for variable_name in (
        "NEWSAPI_API_KEY",
        "NEWS_API_KEY",
        "NEWSAPI_KEY",
    ):
        value = os.getenv(variable_name, "").strip()

        if value:
            return value

    # Preserve compatibility with api_manager.py.
    try:
        settings = get_api_settings()

        for variable_name in (
            "NEWSAPI_API_KEY",
            "NEWS_API_KEY",
            "NEWSAPI_KEY",
        ):
            value = str(
                settings.values.get(
                    variable_name,
                    "",
                )
            ).strip()

            if value:
                return value
    except Exception as exc:
        log.warning(
            "Could not read NewsAPI key from api_manager: %s",
            exc,
        )

    return ""


def _fetch_newsapi(
    query: str,
    api_key: str,
) -> NewsResult:
    response = requests.get(
        NEWSAPI_URL,
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 8,
        },
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
        },
        timeout=15,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        error_code = payload.get(
            "code",
            f"http_{response.status_code}",
        )
        error_message = payload.get(
            "message",
            response.text[:200],
        )

        raise RuntimeError(
            f"{error_code}: {error_message}"
        )

    articles = payload.get("articles", [])

    if not isinstance(articles, list):
        articles = []

    headlines = []

    for article in articles:
        if not isinstance(article, dict):
            continue

        title = str(
            article.get("title") or ""
        ).strip()

        if title and title != "[Removed]":
            headlines.append(title)

    return NewsResult(
        sentiment=_average_sentiment(headlines),
        headlines=headlines,
        source="NewsAPI",
        message=(
            f"NewsAPI returned {len(headlines)} headlines "
            f"for {query}."
        ),
    )


def _fetch_google_news(
    query: str,
) -> NewsResult:
    encoded_query = requests.utils.quote(query)

    url = (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=en-US"
        "&gl=US"
        "&ceid=US:en"
    )

    feed = feedparser.parse(url)

    headlines = [
        str(entry.title).strip()
        for entry in feed.entries[:8]
        if getattr(entry, "title", None)
    ]

    return NewsResult(
        sentiment=_average_sentiment(headlines),
        headlines=headlines,
        source="Google News RSS",
        message=(
            f"Google News returned {len(headlines)} "
            f"headlines for {query}."
        ),
    )


def get_news_sentiment(
    query: str,
) -> NewsResult:
    clean_query = str(query).strip()

    if not ENABLE_NEWS:
        return NewsResult(
            sentiment=0.0,
            headlines=[],
            source="Disabled",
            message="News collection is disabled.",
        )

    if not clean_query:
        return NewsResult(
            sentiment=0.0,
            headlines=[],
            source="Unavailable",
            message="No news query was provided.",
        )

    api_key = _get_newsapi_key()

    if api_key:
        try:
            result = _fetch_newsapi(
                clean_query,
                api_key,
            )

            log.info(
                "NewsAPI success | query=%s | "
                "headlines=%d | sentiment=%.3f",
                clean_query,
                len(result.headlines),
                result.sentiment,
            )

            return result

        except Exception as exc:
            log.warning(
                "NewsAPI failed for %s: %s",
                clean_query,
                exc,
            )
    else:
        log.warning(
            "NewsAPI key is not configured. "
            "Expected NEWSAPI_API_KEY or NEWS_API_KEY."
        )

    try:
        result = _fetch_google_news(
            clean_query
        )

        log.info(
            "Google News fallback success | query=%s | "
            "headlines=%d | sentiment=%.3f",
            clean_query,
            len(result.headlines),
            result.sentiment,
        )

        return result

    except Exception as exc:
        log.warning(
            "Google News fallback failed for %s: %s",
            clean_query,
            exc,
        )

        return NewsResult(
            sentiment=0.0,
            headlines=[],
            source="Unavailable",
            message=str(exc),
        )