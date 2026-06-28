"""Core newsletter creation, shared by the /generate route and the scheduler."""

from datetime import date

from sqlmodel import Session

from models.db import SavedNewsletter
from models.schemas import NewsFilters
from services.llm import generate_newsletter
from services.news_fetcher import fetch_articles


class NoArticlesError(RuntimeError):
    """Raised when the news search returns nothing to write about."""


async def create_newsletter(
    session: Session,
    user_id: int,
    topics: list[str],
    tone: str,
    filters: NewsFilters | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> SavedNewsletter:
    """Fetch news, generate the newsletter, persist it, and return the record.

    Lets NewsFetchError / LLMError propagate; raises NoArticlesError when the
    fetch succeeds but finds nothing. Callers map these to their context
    (HTTP status codes for the route, log lines for the scheduler)."""
    filters = filters or NewsFilters()

    articles = await fetch_articles(topics, from_date, to_date, filters)
    if not articles:
        raise NoArticlesError(
            "No recent articles found for those topics/filters. Try loosening them."
        )

    result = await generate_newsletter(topics, articles, tone)

    record = SavedNewsletter(
        user_id=user_id,
        topics=topics,
        tone=tone,
        markdown=result.markdown,
        subject_options=result.subject_options,
        preview_text=result.preview_text,
        articles=[a.model_dump() for a in articles],
        filters=filters.model_dump(),
        from_date=from_date,
        to_date=to_date,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
