"""FastAPI app entry point for the newsletter generator."""

import os

from dotenv import load_dotenv

# Load backend/.env before anything reads os.environ (SDK clients, services).
load_dotenv()

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from database import init_db  # noqa: E402
from rate_limit import limiter  # noqa: E402
from routes.auth import router as auth_router  # noqa: E402
from routes.newsletter import router as newsletter_router  # noqa: E402
from routes.presets import router as presets_router  # noqa: E402
from routes.subscription import router as subscription_router  # noqa: E402
from scheduler import shutdown_scheduler, start_scheduler  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the database tables and start the subscription scheduler.
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Newsletter Generator", lifespan=lifespan)

# Rate limiting (slowapi): register the limiter and its 429 handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: any localhost port for dev (Vite picks 5174+ when 5173 is taken), plus
# the deployed frontend origin(s) from ALLOWED_ORIGINS (comma-separated).
_allowed = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(newsletter_router)
app.include_router(presets_router)
app.include_router(subscription_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
