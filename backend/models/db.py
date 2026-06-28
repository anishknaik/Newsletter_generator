"""Database (table) models, kept separate from the API request/response schemas."""

from datetime import date, datetime, timezone

from sqlmodel import JSON, Column, Field, SQLModel


class User(SQLModel, table=True):
    """A registered user. Owns their own topics, newsletters, and presets."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SavedNewsletter(SQLModel, table=True):
    """A generated newsletter persisted to the database.

    `topics` and `articles` are stored as JSON columns so we can save the lists
    directly without a separate table.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    topics: list[str] = Field(sa_column=Column(JSON))
    tone: str
    markdown: str
    subject_options: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    preview_text: str | None = None
    articles: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    # The filters/date window this was generated with (for redisplay).
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    from_date: date | None = None
    to_date: date | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class Topic(SQLModel, table=True):
    """A user-added topic, persisted so it stays in the picker across reloads.

    Uniqueness is enforced per-user in application code (see routes), not by a
    DB constraint, so two users can both add the same topic name.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    name: str = Field(index=True)


class FilterPreset(SQLModel, table=True):
    """A saved set of news filters (language, sources, sort, count) for reuse."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    """A user's recurring-newsletter settings (one row per user)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    cadence: str = "off"  # "off" | "daily" | "weekly"
    send_hour: int = 8  # hour of day (UTC) to send, 0-23
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tone: str = "friendly and informative"
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Extra recipient addresses; the account email is always included implicitly.
    recipients: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    last_sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
