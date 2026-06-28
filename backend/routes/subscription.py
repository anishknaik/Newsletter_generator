"""Subscription routes: view/update the recurring-newsletter settings, send now."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from auth import get_current_user
from database import get_session
from models.db import Subscription, User
from models.schemas import (
    EmailResult,
    NewsFilters,
    SubscriptionIn,
    SubscriptionOut,
)
from services.emailer import email_newsletter, recipient_list
from services.llm import LLMError
from services.news_fetcher import NewsFetchError
from services.newsletter_service import NoArticlesError, create_newsletter

router = APIRouter(prefix="/subscription", tags=["subscription"])


def _to_out(sub: Subscription) -> SubscriptionOut:
    return SubscriptionOut(
        cadence=sub.cadence,
        send_hour=sub.send_hour,
        topics=sub.topics,
        tone=sub.tone,
        filters=NewsFilters(**sub.filters),
        recipients=sub.recipients,
        last_sent_at=sub.last_sent_at,
    )


def _get_sub(session: Session, user_id: int) -> Subscription | None:
    return session.exec(
        select(Subscription).where(Subscription.user_id == user_id)
    ).first()


@router.get("", response_model=SubscriptionOut)
def get_subscription(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> SubscriptionOut:
    """Return the user's subscription, or sensible defaults if none exists yet."""
    sub = _get_sub(session, user.id)
    return _to_out(sub) if sub else SubscriptionOut()


@router.put("", response_model=SubscriptionOut)
def update_subscription(
    req: SubscriptionIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SubscriptionOut:
    """Create or update the user's subscription settings."""
    if req.cadence != "off" and not req.topics:
        raise HTTPException(
            status_code=400, detail="Pick at least one topic to schedule a newsletter."
        )

    sub = _get_sub(session, user.id)
    if sub is None:
        sub = Subscription(user_id=user.id)
        session.add(sub)

    sub.cadence = req.cadence
    sub.send_hour = req.send_hour
    sub.topics = req.topics
    sub.tone = req.tone
    sub.filters = req.filters.model_dump()
    sub.recipients = [str(r) for r in req.recipients]
    session.commit()
    session.refresh(sub)
    return _to_out(sub)


@router.post("/send-now", response_model=EmailResult)
async def send_now(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> EmailResult:
    """Generate and email a newsletter immediately using the saved settings."""
    sub = _get_sub(session, user.id)
    if sub is None or not sub.topics:
        raise HTTPException(
            status_code=400,
            detail="Set up your subscription topics first, then send.",
        )

    try:
        record = await create_newsletter(
            session, user.id, sub.topics, sub.tone, NewsFilters(**sub.filters)
        )
    except NoArticlesError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (NewsFetchError, LLMError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        status = email_newsletter(recipient_list(user.email, sub.recipients), record)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Email failed: {exc}") from exc

    sub.last_sent_at = datetime.now(timezone.utc)
    session.commit()
    return EmailResult(status=status)
