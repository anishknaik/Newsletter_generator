"""API routes: /topics, /generate, and saved-newsletter CRUD (all per-user)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from auth import get_current_user
from rate_limit import limiter
from database import get_session
from models.db import SavedNewsletter, Topic, User
from models.schemas import (
    AddTopicRequest,
    EmailRequest,
    EmailResult,
    GenerateRequest,
    GenerateResponse,
    SavedDetail,
    SavedSummary,
    TopicsResponse,
)
from services.emailer import email_newsletter
from services.llm import LLMError
from services.news_fetcher import NewsFetchError
from services.newsletter_service import NoArticlesError, create_newsletter

router = APIRouter()

# Built-in defaults for the topic picker. Each user can also add their own,
# which get persisted (scoped to that user) and merged in below.
SUGGESTED_TOPICS = [
    "Artificial Intelligence",
    "Climate",
    "Space",
    "Finance",
    "Health",
    "Technology",
    "Sports",
    "Politics",
    "Science",
    "Entertainment",
]


def _user_topic_names(session: Session, user_id: int) -> list[str]:
    """Defaults first, then this user's added topics not already in the defaults."""
    names = list(SUGGESTED_TOPICS)
    rows = session.exec(
        select(Topic).where(Topic.user_id == user_id).order_by(Topic.id)
    ).all()
    for topic in rows:
        if topic.name not in names:
            names.append(topic.name)
    return names


@router.get("/topics", response_model=TopicsResponse)
def get_topics(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> TopicsResponse:
    """Return the built-in plus this user's topics for the picker UI."""
    return TopicsResponse(topics=_user_topic_names(session, user.id))


@router.post("/topics", response_model=TopicsResponse)
def add_topic(
    req: AddTopicRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TopicsResponse:
    """Persist a custom topic for this user. Idempotent."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Topic name is required.")

    already_known = name in SUGGESTED_TOPICS or session.exec(
        select(Topic).where(Topic.user_id == user.id, Topic.name == name)
    ).first()
    if not already_known:
        session.add(Topic(name=name, user_id=user.id))
        session.commit()

    return TopicsResponse(topics=_user_topic_names(session, user.id))


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("20/hour")
async def generate(
    request: Request,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> GenerateResponse:
    """Fetch news, generate a newsletter, persist it for the user, and return it."""
    try:
        record = await create_newsletter(
            session, user.id, req.topics, req.tone, req.filters,
            req.from_date, req.to_date,
        )
    except NoArticlesError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (NewsFetchError, LLMError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface any other error to the client
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    return GenerateResponse(
        id=record.id,
        markdown=record.markdown,
        subject_options=record.subject_options,
        preview_text=record.preview_text,
        topics=record.topics,
        articles=record.articles,
        filters=record.filters or None,
        from_date=record.from_date,
        to_date=record.to_date,
    )


def _owned_or_404(
    newsletter_id: int, user: User, session: Session
) -> SavedNewsletter:
    """Fetch a newsletter, 404ing if it doesn't exist or isn't this user's."""
    record = session.get(SavedNewsletter, newsletter_id)
    if not record or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Newsletter not found.")
    return record


@router.get("/newsletters", response_model=list[SavedSummary])
def list_newsletters(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[SavedNewsletter]:
    """List this user's saved newsletters, most recent first (without the body)."""
    return session.exec(
        select(SavedNewsletter)
        .where(SavedNewsletter.user_id == user.id)
        .order_by(SavedNewsletter.created_at.desc())
    ).all()


@router.get("/newsletters/{newsletter_id}", response_model=SavedDetail)
def get_newsletter(
    newsletter_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SavedNewsletter:
    """Fetch one of the user's saved newsletters in full."""
    return _owned_or_404(newsletter_id, user, session)


@router.delete("/newsletters/{newsletter_id}", status_code=204)
def delete_newsletter(
    newsletter_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete one of the user's saved newsletters."""
    record = _owned_or_404(newsletter_id, user, session)
    session.delete(record)
    session.commit()


@router.post("/newsletters/{newsletter_id}/email", response_model=EmailResult)
def email_one(
    newsletter_id: int,
    req: EmailRequest | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> EmailResult:
    """Email a saved newsletter to a given address, or the account email."""
    record = _owned_or_404(newsletter_id, user, session)
    to = (req.to if req else None) or user.email
    try:
        status = email_newsletter(to, record)
    except Exception as exc:  # noqa: BLE001 — surface SMTP errors to the client
        raise HTTPException(status_code=502, detail=f"Email failed: {exc}") from exc
    return EmailResult(status=status)
