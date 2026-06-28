"""Pytest fixtures: an isolated in-memory DB and mocked external services.

The NewsAPI and OpenRouter calls are replaced with fast fakes so the suite is
deterministic and needs no network or API keys.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import main
import rate_limit
import services.emailer as emailer
import services.newsletter_service as svc
from database import get_session
from models.schemas import Article
from services.llm import GeneratedNewsletter


@pytest.fixture(name="engine")
def engine_fixture():
    # One shared in-memory SQLite connection for the whole test (StaticPool).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine


@pytest.fixture(name="client")
def client_fixture(engine, monkeypatch, tmp_path):
    def get_session_override():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[get_session] = get_session_override

    async def fake_fetch(topics, from_date=None, to_date=None, filters=None):
        size = filters.page_size if filters else 5
        return [
            Article(
                title=f"{topic} headline {i}",
                description=f"About {topic}.",
                url=f"https://example.com/{topic}/{i}",
                image_url="https://example.com/img.jpg",
                source="Example",
                topic=topic,
            )
            for topic in topics
            for i in range(size)
        ]

    async def fake_generate(topics, articles, tone):
        body = "## TL;DR\n- point one\n\n## " + topics[0] + "\nSome body."
        return GeneratedNewsletter(
            markdown=body,
            subject_options=["Subject A", "Subject B", "Subject C"],
            preview_text="A quick preview.",
        )

    # Generation flows through the service module, so patch its names there.
    monkeypatch.setattr(svc, "fetch_articles", fake_fetch)
    monkeypatch.setattr(svc, "generate_newsletter", fake_generate)
    # Email in dev mode, writing to a temp outbox.
    monkeypatch.setattr(emailer, "OUTBOX", tmp_path / "outbox")
    monkeypatch.setenv("SMTP_HOST", "")
    # Disable rate limiting by default; the rate-limit test re-enables it.
    rate_limit.limiter.enabled = False

    # No `with` block: we don't want the lifespan to touch the real database.
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def auth(client):
    """Factory that registers a fresh user and returns auth headers."""
    counter = {"n": 0}

    def _make():
        counter["n"] += 1
        email = f"user{counter['n']}@example.com"
        r = client.post("/auth/register", json={"email": email, "password": "secret123"})
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make
