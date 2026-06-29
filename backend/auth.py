"""Authentication helpers: password hashing, JWT tokens, current-user dependency."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from database import get_session
from models.db import User

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=7)

# Extracts "Authorization: Bearer <token>" from requests.
_bearer = HTTPBearer()


def _secret() -> str:
    # Read lazily so .env (loaded in main.py) is already applied.
    return os.environ.get("JWT_SECRET", "dev-insecure-change-me")


def validate_password(password: str) -> None:
    """Enforce basic password strength, raising a clean 400 if it's too weak."""
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters."
        )
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must include at least one letter and one number.",
        )


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    """Decode the bearer token and return the matching user, or raise 401."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise invalid from exc

    user = session.get(User, user_id)
    if user is None:
        raise invalid
    # Release the DB connection right after auth so it isn't held open (idle in a
    # transaction) across slow work in the route — e.g. the LLM call in /generate,
    # which managed Postgres like Neon would drop. The detached user keeps its
    # already-loaded fields; the route re-acquires a fresh connection when it writes.
    session.close()
    return user
