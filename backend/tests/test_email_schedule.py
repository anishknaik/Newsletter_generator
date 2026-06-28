"""Tests for email delivery, subscriptions, send-now, and the due-check."""

from datetime import datetime, timedelta, timezone

from models.db import SavedNewsletter
from scheduler import is_due
from services.emailer import render_email_html

UTC = timezone.utc


def test_email_html_constrains_image_width():
    """Article images must be inline-constrained so they don't overflow the email."""
    nl = SavedNewsletter(
        topics=["Tech"], tone="x", markdown="![](https://x/y.jpg)",
        subject_options=["S"], preview_text="p", articles=[],
        created_at=datetime.now(UTC),
    )
    html = render_email_html(nl)
    assert '<img style="max-width:100%' in html


# --- Emailing a saved newsletter ---

def test_email_saved_newsletter_dev_mode(client, auth):
    a = auth()
    nid = client.post("/generate", headers=a, json={"topics": ["Tech"]}).json()["id"]
    r = client.post(f"/newsletters/{nid}/email", headers=a)
    assert r.status_code == 200
    assert "dev mode" in r.json()["status"]


def test_email_other_users_newsletter_404(client, auth):
    a, b = auth(), auth()
    nid = client.post("/generate", headers=a, json={"topics": ["Tech"]}).json()["id"]
    assert client.post(f"/newsletters/{nid}/email", headers=b).status_code == 404


def test_email_to_custom_address(client, auth):
    a = auth()
    nid = client.post("/generate", headers=a, json={"topics": ["Tech"]}).json()["id"]
    r = client.post(f"/newsletters/{nid}/email", headers=a, json={"to": "friend@example.com"})
    assert r.status_code == 200
    assert "friend@example.com" in r.json()["status"]


def test_subscription_recipients_persist(client, auth):
    a = auth()
    client.put("/subscription", headers=a, json={
        "cadence": "off", "topics": ["Tech"],
        "recipients": ["one@example.com", "two@example.com"],
    })
    again = client.get("/subscription", headers=a).json()
    assert again["recipients"] == ["one@example.com", "two@example.com"]


def test_send_now_fans_out_to_recipients(client, auth):
    a = auth()
    client.put("/subscription", headers=a, json={
        "cadence": "off", "topics": ["Tech"],
        "recipients": ["one@example.com", "two@example.com"],
    })
    r = client.post("/subscription/send-now", headers=a)
    assert r.status_code == 200
    # account email + 2 extras = 3 recipients → "+2 more".
    assert "+2 more" in r.json()["status"]


# --- Subscription settings ---

def test_subscription_defaults(client, auth):
    a = auth()
    sub = client.get("/subscription", headers=a).json()
    assert sub["cadence"] == "off"
    assert sub["last_sent_at"] is None


def test_subscription_update_and_persist(client, auth):
    a = auth()
    r = client.put("/subscription", headers=a, json={
        "cadence": "weekly", "send_hour": 9, "topics": ["Tech", "Space"],
        "tone": "witty",
        "filters": {"language": "en", "sort_by": "popularity", "page_size": 6,
                    "domains": [], "exclude_domains": []},
    })
    assert r.status_code == 200 and r.json()["cadence"] == "weekly"
    again = client.get("/subscription", headers=a).json()
    assert again["topics"] == ["Tech", "Space"] and again["send_hour"] == 9
    assert again["filters"]["page_size"] == 6


def test_subscription_requires_topics_when_on(client, auth):
    a = auth()
    r = client.put("/subscription", headers=a, json={"cadence": "daily", "topics": []})
    assert r.status_code == 400


# --- Send now ---

def test_send_now_requires_setup(client, auth):
    a = auth()
    assert client.post("/subscription/send-now", headers=a).status_code == 400


def test_send_now_generates_and_emails(client, auth):
    a = auth()
    client.put("/subscription", headers=a, json={"cadence": "off", "topics": ["Tech"]})
    r = client.post("/subscription/send-now", headers=a)
    assert r.status_code == 200 and "dev mode" in r.json()["status"]
    # last_sent_at is now recorded.
    assert client.get("/subscription", headers=a).json()["last_sent_at"] is not None


# --- Due-check (pure function) ---

def test_is_due_off_never_sends():
    now = datetime(2026, 6, 27, 10, tzinfo=UTC)
    assert is_due("off", 8, None, now) is False


def test_is_due_waits_for_send_hour():
    now = datetime(2026, 6, 27, 7, tzinfo=UTC)  # before 8:00
    assert is_due("daily", 8, None, now) is False


def test_is_due_daily_once_per_day():
    now = datetime(2026, 6, 27, 9, tzinfo=UTC)
    assert is_due("daily", 8, None, now) is True  # never sent
    sent_today = datetime(2026, 6, 27, 8, 30, tzinfo=UTC)
    assert is_due("daily", 8, sent_today, now) is False
    sent_yesterday = datetime(2026, 6, 26, 8, 30, tzinfo=UTC)
    assert is_due("daily", 8, sent_yesterday, now) is True


def test_is_due_weekly_every_seven_days():
    now = datetime(2026, 6, 27, 9, tzinfo=UTC)
    assert is_due("weekly", 8, now - timedelta(days=7), now) is True
    assert is_due("weekly", 8, now - timedelta(days=3), now) is False
