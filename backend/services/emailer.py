"""Email delivery: render a newsletter to an HTML email and send it.

Transport is chosen at send time:
  1. RESEND_API_KEY set  -> Resend HTTP API (works on hosts that block SMTP, e.g. Render)
  2. SMTP_HOST set       -> SMTP (good for local dev with a Gmail App Password)
  3. neither             -> dev mode: write the email to backend/outbox/ as .html
"""

import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import httpx
import markdown as md

from models.db import SavedNewsletter

OUTBOX = Path(__file__).resolve().parent.parent / "outbox"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "newsletter"


def render_email_html(newsletter: SavedNewsletter) -> str:
    """Render a saved newsletter into a standalone, styled HTML email."""
    subject = newsletter.subject_options[0] if newsletter.subject_options else "Your newsletter"
    issue_date = (newsletter.created_at or datetime.now(timezone.utc)).strftime("%B %d, %Y")
    body_html = md.markdown(newsletter.markdown or "", extensions=["extra", "sane_lists"])
    # Email clients ignore most <style> rules, so inline the image sizing on each
    # <img> tag — otherwise full-size article images overflow the newsletter border.
    body_html = re.sub(
        r"<img ",
        '<img style="max-width:100%;height:auto;display:block;'
        'border-radius:8px;margin:12px 0;" ',
        body_html,
    )
    preview = newsletter.preview_text or ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{subject}</title></head>
<body style="margin:0;background:#f7f6f2;padding:24px;
             font-family:Georgia,'Times New Roman',serif;color:#1c1b19;">
  <div style="max-width:640px;margin:0 auto;background:#fff;border:1px solid #e3e0d8;
              border-radius:10px;padding:24px 28px;line-height:1.65;">
    <div style="display:flex;justify-content:space-between;align-items:baseline;
                border-bottom:3px double #1c1b19;padding-bottom:8px;margin-bottom:14px;">
      <span style="font-size:1.5rem;font-weight:bold;">📰 The Brief</span>
      <span style="font-size:.8rem;color:#6b6862;text-transform:uppercase;">
        {issue_date} · {' · '.join(newsletter.topics)}</span>
    </div>
    <h2 style="margin:0 0 .25rem;">{subject}</h2>
    <p style="color:#6b6862;font-style:italic;margin:0 0 1rem;">{preview}</p>
    {body_html}
    <hr style="border:none;border-top:1px solid #e3e0d8;margin:1.5rem 0 .75rem;">
    <p style="font-size:.8rem;color:#6b6862;text-align:center;">
      You're receiving this from Newsletter Generator.</p>
  </div>
</body></html>"""


def _send_via_resend(recipients: list[str], subject: str, html: str, api_key: str) -> None:
    """Send through Resend's HTTPS API (port 443) — not blocked like SMTP is."""
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            # On Resend's free tier without a verified domain this must be an
            # onboarding@resend.dev sender; override via RESEND_FROM once verified.
            "from": os.environ.get("RESEND_FROM", "Newsletter Generator <onboarding@resend.dev>"),
            "to": recipients,
            "subject": subject,
            "html": html,
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend {resp.status_code}: {resp.text[:300]}")


def send_email(to: str | list[str], subject: str, html: str) -> str:
    """Send an HTML email to one or more recipients, or write it to the outbox
    in dev mode. Returns a short status string for the API/scheduler logs."""
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        return "no recipients — nothing sent"
    who = recipients[0] + (f" +{len(recipients) - 1} more" if len(recipients) > 1 else "")

    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    if resend_key:
        _send_via_resend(recipients, subject, html, resend_key)
        return f"sent to {who} via Resend"

    host = os.environ.get("SMTP_HOST", "").strip()

    if not host:
        OUTBOX.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = OUTBOX / f"{stamp}-{_slugify(recipients[0])}.html"
        path.write_text(html, encoding="utf-8")
        return f"dev mode — wrote email for {who} to outbox/{path.name} (set SMTP_* in .env to send for real)"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("EMAIL_FROM", "Newsletter Generator <no-reply@example.com>")
    msg["To"] = ", ".join(recipients)
    msg.set_content("This newsletter is best viewed in an HTML email client.")
    msg.add_alternative(html, subtype="html")

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "")
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls(context=ssl.create_default_context())
        if user:
            server.login(user, password)
        server.send_message(msg)
    return f"sent to {who} via {host}"


def recipient_list(account_email: str, extra: list[str]) -> list[str]:
    """Account email first, then any extra recipients, de-duplicated."""
    out = [account_email]
    for addr in extra:
        if addr and addr not in out:
            out.append(addr)
    return out


def email_newsletter(to: str | list[str], newsletter: SavedNewsletter) -> str:
    """Convenience wrapper: render + send a saved newsletter to one or more addresses."""
    subject = newsletter.subject_options[0] if newsletter.subject_options else "Your newsletter"
    return send_email(to, subject, render_email_html(newsletter))
