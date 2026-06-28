"""Pydantic request/response models for the newsletter API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SortBy = Literal["publishedAt", "relevancy", "popularity"]


class Article(BaseModel):
    """A single news article pulled from NewsAPI."""

    title: str
    description: str | None = None
    url: str
    image_url: str | None = None
    source: str | None = None
    published_at: str | None = None
    topic: str


class NewsFilters(BaseModel):
    """Tunable knobs for the NewsAPI search (saved in presets, reused later)."""

    language: str = Field(default="en", max_length=5)
    sort_by: SortBy = "publishedAt"
    page_size: int = Field(default=5, ge=1, le=20, description="Articles per topic.")
    domains: list[str] = Field(default_factory=list, description="Only these domains.")
    exclude_domains: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    """Body for POST /generate — the topics the user picked, plus filters."""

    topics: list[str] = Field(..., min_length=1, max_length=10)
    tone: str = Field(
        default="friendly and informative",
        description="Optional voice for the newsletter, e.g. 'witty', 'formal'.",
    )
    # Optional date window for the news search (NewsAPI free tier only reaches
    # back ~1 month). Both inclusive; omit for the latest news.
    from_date: date | None = None
    to_date: date | None = None
    filters: NewsFilters = Field(default_factory=NewsFilters)


# --- Auth ---


class RegisterRequest(BaseModel):
    email: EmailStr
    # Strength is enforced in auth.validate_password so the error is a clean 400.
    password: str = Field(..., max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    # from_attributes lets us build this straight from a User ORM object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Filter presets ---


class PresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    filters: NewsFilters


class PresetOut(BaseModel):
    id: int
    name: str
    filters: NewsFilters
    created_at: datetime


# --- Email + subscriptions ---

Cadence = Literal["off", "daily", "weekly"]


class EmailResult(BaseModel):
    """Status returned after attempting to send/queue an email."""

    status: str


class EmailRequest(BaseModel):
    """Optional recipient override when emailing a single issue."""

    to: EmailStr | None = None


class SubscriptionIn(BaseModel):
    cadence: Cadence = "off"
    send_hour: int = Field(default=8, ge=0, le=23)
    topics: list[str] = Field(default_factory=list, max_length=10)
    tone: str = "friendly and informative"
    filters: NewsFilters = Field(default_factory=NewsFilters)
    # Extra addresses to also receive the newsletter (the account email always does).
    recipients: list[EmailStr] = Field(default_factory=list, max_length=20)


class SubscriptionOut(SubscriptionIn):
    last_sent_at: datetime | None = None


class AddTopicRequest(BaseModel):
    """Body for POST /topics — a custom topic to persist."""

    name: str = Field(..., min_length=1, max_length=60)


class GenerateResponse(BaseModel):
    """What the API returns: the saved id, newsletter, and source articles."""

    id: int
    markdown: str
    subject_options: list[str] = Field(default_factory=list)
    preview_text: str | None = None
    topics: list[str]
    articles: list[Article]
    filters: NewsFilters | None = None
    from_date: date | None = None
    to_date: date | None = None


class TopicsResponse(BaseModel):
    """Suggested topics for the picker UI."""

    topics: list[str]


class SavedSummary(BaseModel):
    """Lightweight row for the saved-newsletters list (no body)."""

    id: int
    topics: list[str]
    tone: str
    preview_text: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    created_at: datetime


class SavedDetail(BaseModel):
    """A full saved newsletter, for reopening one from the list."""

    id: int
    topics: list[str]
    tone: str
    markdown: str
    subject_options: list[str] = Field(default_factory=list)
    preview_text: str | None = None
    articles: list[Article]
    filters: NewsFilters | None = None
    from_date: date | None = None
    to_date: date | None = None
    created_at: datetime
