"""Background scheduler that emails due subscriptions.

A single job ticks every 15 minutes, finds subscriptions that are due, and for
each one generates a fresh newsletter and emails it. The due-check is a pure
function (`is_due`) so it can be unit-tested without time or a database.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from models.db import Subscription, User
from models.schemas import NewsFilters
from services.emailer import email_newsletter, recipient_list
from services.newsletter_service import create_newsletter

_scheduler = BackgroundScheduler(timezone="UTC")


def is_due(
    cadence: str,
    send_hour: int,
    last_sent_at: datetime | None,
    now: datetime,
) -> bool:
    """Should a subscription send right now? Pure and timezone-aware.

    Only sends at/after the configured hour, and never more than once per
    period (day for daily, 7 days for weekly)."""
    if cadence == "off" or now.hour < send_hour:
        return False
    if last_sent_at is None:
        return True
    if cadence == "daily":
        return last_sent_at.date() < now.date()
    if cadence == "weekly":
        return (now - last_sent_at) >= timedelta(days=7)
    return False


async def _process_due() -> None:
    from database import engine

    now = datetime.now(timezone.utc)

    # Pass 1 (quick reads): collect the data for every due subscription.
    due: list[dict] = []
    with Session(engine) as session:
        subs = session.exec(
            select(Subscription).where(Subscription.cadence != "off")
        ).all()
        for sub in subs:
            last = sub.last_sent_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)  # SQLite returns naive
            if not sub.topics or not is_due(sub.cadence, sub.send_hour, last, now):
                continue
            user = session.get(User, sub.user_id)
            if user is None:
                continue
            due.append({
                "id": sub.id, "user_id": sub.user_id, "email": user.email,
                "topics": list(sub.topics), "tone": sub.tone,
                "filters": NewsFilters(**sub.filters),
                "recipients": list(sub.recipients),
            })

    # Pass 2 (slow): generate + email each with short-lived sessions, so no DB
    # connection is held idle across the LLM call.
    for d in due:
        try:
            with Session(engine) as session:
                record = await create_newsletter(
                    session, d["user_id"], d["topics"], d["tone"], d["filters"]
                )
            email_newsletter(recipient_list(d["email"], d["recipients"]), record)
            with Session(engine) as session:
                sub = session.get(Subscription, d["id"])
                if sub:
                    sub.last_sent_at = now
                    session.commit()
            print(f"[scheduler] sent newsletter to {d['email']}")
        except Exception as exc:  # noqa: BLE001 — one failure shouldn't stop the rest
            print(f"[scheduler] subscription {d['id']} failed: {exc}")


def _tick() -> None:
    # APScheduler runs jobs in a thread; spin up an event loop for the async work.
    asyncio.run(_process_due())


def start_scheduler() -> None:
    if _scheduler.running:
        return
    _scheduler.add_job(_tick, "interval", minutes=15, id="tick", replace_existing=True)
    _scheduler.start()


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
