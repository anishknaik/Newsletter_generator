"""Fetch recent articles per topic from NewsAPI."""

import os
from datetime import date

import httpx

from models.schemas import Article, NewsFilters

NEWSAPI_URL = "https://newsapi.org/v2/everything"


class NewsFetchError(RuntimeError):
    """Raised when NewsAPI can't be reached or rejects the request."""


async def fetch_articles(
    topics: list[str],
    from_date: date | None = None,
    to_date: date | None = None,
    filters: NewsFilters | None = None,
) -> list[Article]:
    """Query NewsAPI once per topic and return a flat list of articles.

    `from_date`/`to_date` optionally restrict the search window (NewsAPI's free
    tier only reaches back ~1 month). `filters` tunes language, sort order,
    article count, and which domains to include/exclude. A failure on one topic
    doesn't sink the whole request — we collect what we can and only raise if
    every topic fails (so the caller can surface a useful error instead of
    generating a newsletter from nothing).
    """
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        raise NewsFetchError("NEWSAPI_KEY is not set. Copy backend/.env.example to .env.")

    filters = filters or NewsFilters()
    articles: list[Article] = []
    failures = 0

    # Shared params for every topic; only the query term changes per loop.
    base_params: dict[str, object] = {
        "language": filters.language,
        "sortBy": filters.sort_by,
        "pageSize": filters.page_size,
        "apiKey": api_key,
    }
    if filters.domains:
        base_params["domains"] = ",".join(filters.domains)
    if filters.exclude_domains:
        base_params["excludeDomains"] = ",".join(filters.exclude_domains)
    if from_date:
        base_params["from"] = from_date.isoformat()
    if to_date:
        base_params["to"] = to_date.isoformat()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for topic in topics:
            try:
                resp = await client.get(NEWSAPI_URL, params={**base_params, "q": topic})
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                failures += 1
                # NewsAPI returns a JSON error body on 4xx — surface its message.
                detail = ""
                if isinstance(exc, httpx.HTTPStatusError):
                    detail = exc.response.json().get("message", "")
                print(f"[news_fetcher] topic '{topic}' failed: {exc} {detail}")
                continue

            for raw in resp.json().get("articles", []):
                articles.append(
                    Article(
                        title=raw.get("title") or "(untitled)",
                        description=raw.get("description"),
                        url=raw.get("url") or "",
                        image_url=raw.get("urlToImage"),
                        source=(raw.get("source") or {}).get("name"),
                        published_at=raw.get("publishedAt"),
                        topic=topic,
                    )
                )

    if failures == len(topics):
        raise NewsFetchError("Every topic failed to fetch from NewsAPI. Check your key and quota.")

    return articles
