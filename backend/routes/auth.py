"""Auth routes: register, login, and the current-user lookup."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    validate_password,
    verify_password,
)
from database import get_session
from models.db import User
from models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/hour")
def register(
    request: Request, req: RegisterRequest, session: Session = Depends(get_session)
) -> TokenResponse:
    """Create an account and return a login token."""
    validate_password(req.password)
    email = req.email.lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="That email is already registered.")

    user = User(email=email, hashed_password=hash_password(req.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request, req: LoginRequest, session: Session = Depends(get_session)
) -> TokenResponse:
    """Verify credentials and return a login token."""
    user = session.exec(select(User).where(User.email == req.email.lower())).first()
    if user is None or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    return TokenResponse(access_token=create_access_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the currently logged-in user (used to validate a stored token)."""
    return user
