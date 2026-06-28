# Newsletter Generator

[![CI](https://github.com/anishknaik/Newsletter_generator/actions/workflows/ci.yml/badge.svg)](https://github.com/anishknaik/Newsletter_generator/actions/workflows/ci.yml)

Pick a few topics → the app pulls recent news on them → a free LLM writes a
coherent newsletter → you read it in the browser.

- **Backend:** FastAPI (Python), NewsAPI for articles, OpenRouter for writing.
- **Frontend:** React + Vite.

Features: email/password accounts (JWT), per-user topics & newsletters, a topic
picker with persistent custom topics, tunable news filters (language, sort,
article count, include/exclude domains) saved as reusable presets, an optional
date window, structured output (subject lines, preview text, TL;DR, images,
masthead/footer), generated newsletters auto-saved to SQLite (search/reopen/
delete), Markdown/HTML export, and **email delivery + scheduling** — email any
issue to yourself or schedule a daily/weekly newsletter.

## Prerequisites

- Python 3.10+
- Node 18+
- A free [NewsAPI](https://newsapi.org/register) key
- A free [OpenRouter](https://openrouter.ai/keys) key
- A `JWT_SECRET` for signing login tokens (any long random string; see `.env.example`)

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit .env and paste in your two keys
uvicorn main:app --reload   # serves on http://localhost:8000
```

Sanity check: open <http://localhost:8000/health> — you should see `{"status":"ok"}`.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev                 # serves on http://localhost:5173
```

Open <http://localhost:5173>, pick topics, and hit **Generate newsletter**.

## How it fits together

```
TopicSelector → POST /generate
                  ├─ news_fetcher.py  → NewsAPI (recent articles per topic)
                  └─ llm.py           → OpenRouter (free LLM) writes the newsletter
                ← { markdown, articles } → NewsletterPreview renders it
```

## Notes

- Free models are constantly rate-limited, so [backend/services/llm.py](backend/services/llm.py)
  holds a `MODELS` list and tries each in order, falling through to the next on any
  failure (429, unavailable, etc.). Add/reorder free models from
  <https://openrouter.ai/models?max_price=0>. If `/generate` returns a 502, every
  model in the list was rate-limited — wait a bit or add more. Edit the
  `SYSTEM_PROMPT` there to adjust voice or format.
- `.env` holds the API keys and `JWT_SECRET` and is gitignored — never commit it.
- NewsAPI's free tier only covers articles from roughly the last month and is
  rate-limited; if `/generate` returns a 502, check your key and quota.
- **Email:** if `SMTP_HOST` is blank in `.env`, the app runs in *dev mode* and
  writes each email to `backend/outbox/` (also gitignored) instead of sending —
  open the `.html` file to preview it. Set `SMTP_HOST/PORT/USER/PASS` (e.g. a
  Gmail App Password) to send for real.
- **Scheduling:** an in-process APScheduler job checks every 15 minutes and sends
  any due subscriptions. Configure cadence/hour/topics from the "Schedule" panel,
  or use **Send now** for an immediate run.
- **Recipients:** email any saved issue to a one-off address (the ✉ Email field),
  or add a recipient list in the Schedule panel so scheduled/Send-now issues fan
  out to everyone. Your account email is always included.
- **Security:** auth and `/generate` are rate-limited (slowapi, in-memory — swap to
  Redis storage for multi-worker deploys), passwords require 8+ chars with a letter
  and a number, and an expired session bounces to login with a notice.
- **Tests:** `cd backend && python -m pytest tests/ -q` (mocks NewsAPI/OpenRouter,
  uses an in-memory DB — no keys or network needed).

## Deploy (Render backend + Vercel frontend)

The backend reads `DATABASE_URL`, `ALLOWED_ORIGINS`, and the usual keys from the
environment; the frontend reads `VITE_API_URL` at build time.

**0. Before a public repo:** rotate the NewsAPI / OpenRouter / Gmail App Password
keys, since real keys are never committed but should be fresh for production. Set
the new values as host env vars (never in the repo).

**1. Push to GitHub**
```bash
git init && git add . && git commit -m "Newsletter generator"
gh repo create newsletter-generator --public --source=. --push
```

**2. Backend on Render** (uses [render.yaml](render.yaml))
- New → Blueprint → pick the repo. Render reads `render.yaml` (Python web service,
  `rootDir: backend`, 1 GB disk at `/var/data`, SQLite stored there).
- Fill the dashboard secrets: `NEWSAPI_KEY`, `OPENROUTER_API_KEY`, `SMTP_*`,
  `EMAIL_FROM`, and `ALLOWED_ORIGINS` (your Vercel URL — set after step 3).
- Note: the persistent disk requires a paid **Starter** instance; on the free tier
  the SQLite file resets on each deploy.

**3. Frontend on Vercel**
- New Project → import the repo → set **Root Directory** to `frontend`
  (framework auto-detects as Vite).
- Add env var `VITE_API_URL` = your Render backend URL (e.g.
  `https://newsletter-backend.onrender.com`), then deploy.

**4. Wire them together**
- Put the Vercel URL into Render's `ALLOWED_ORIGINS` and redeploy the backend so
  CORS accepts the frontend.

## License

MIT — see [LICENSE](LICENSE).
