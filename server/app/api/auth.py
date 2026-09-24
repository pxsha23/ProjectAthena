"""Auth: email + password with JWT cookies, refresh-token rotation, and GitHub OAuth."""

import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import (
    OAUTH_STATE_COOKIE,
    REFRESH_COOKIE,
    TokenError,
    clear_auth_cookies,
    create_token,
    decode_token,
    encrypt_secret,
    hash_password,
    hash_token_id,
    set_auth_cookies,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.api import LoginIn, RegisterIn, UserOut
from app.services import github

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_SCOPES = "read:user user:email repo"


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.has_github_token = user.github_token_encrypted is not None
    return out


async def issue_session(db: DbSession, response: Response, user: User) -> None:
    access, _ = create_token(user.id, "access")
    refresh, jti = create_token(user.id, "refresh")
    db.add(
        RefreshToken(
            id=hash_token_id(jti),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await db.commit()
    set_auth_cookies(response, access, refresh)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, db: DbSession, response: Response) -> UserOut:
    email = body.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    await issue_session(db, response, user)
    return user_out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, db: DbSession, response: Response) -> UserOut:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    await issue_session(db, response, user)
    return user_out(user)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    db: DbSession,
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> UserOut:
    """Rotates the refresh token: the old one is revoked and a new pair is issued."""
    try:
        payload = decode_token(refresh_cookie, "refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    stored = await db.get(RefreshToken, hash_token_id(payload["jti"]))
    if stored is None or stored.revoked or stored.expires_at < utcnow():
        # A revoked token being reused suggests theft: revoke every session for this user.
        if stored is not None and stored.revoked:
            for token in await db.scalars(select(RefreshToken).where(RefreshToken.user_id == stored.user_id)):
                token.revoked = True
            await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired, please sign in again")
    stored.revoked = True
    user = await db.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    await issue_session(db, response, user)
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: DbSession,
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    try:
        payload = decode_token(refresh_cookie, "refresh")
        stored = await db.get(RefreshToken, hash_token_id(payload["jti"]))
        if stored:
            stored.revoked = True
            await db.commit()
    except TokenError:
        pass
    response.status_code = status.HTTP_204_NO_CONTENT
    clear_auth_cookies(response)
    return response


@router.get("/providers")
async def providers() -> dict[str, bool]:
    """Which sign-in methods are configured, so the login page can hide unavailable ones."""
    settings = get_settings()
    return {"github": bool(settings.github_client_id and settings.github_client_secret)}


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return user_out(user)


# ---------------------------------------------------------------- GitHub OAuth


def _require_github() -> None:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub sign-in is not configured: set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET",
        )


@router.get("/github/login")
async def github_login() -> RedirectResponse:
    _require_github()
    settings = get_settings()
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": GITHUB_SCOPES,
            "state": state,
        }
    )
    response = RedirectResponse(f"{settings.github_oauth_url}/authorize?{query}")
    response.set_cookie(
        OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )
    return response


@router.get("/github/callback")
async def github_callback(
    request: Request, db: DbSession, code: str | None = None, state: str | None = None
) -> RedirectResponse:
    _require_github()
    settings = get_settings()
    expected = request.cookies.get(OAUTH_STATE_COOKIE)
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        return RedirectResponse(f"{settings.frontend_url}/login?error=github_state")

    try:
        token = await github.exchange_code(code)
        profile = await github.fetch_user(token)
    except github.GitHubError:
        return RedirectResponse(f"{settings.frontend_url}/login?error=github_failed")

    user = await db.scalar(select(User).where(User.github_id == profile.id))
    if user is None and profile.email:
        # Link to an existing email account with the same verified address.
        user = await db.scalar(select(User).where(User.email == profile.email.lower()))
    if user is None:
        user = User(
            email=profile.email.lower() if profile.email else None, name=profile.name or profile.login
        )
        db.add(user)
    user.github_id, user.github_login = profile.id, profile.login
    user.github_token_encrypted = encrypt_secret(token)
    await db.flush()

    response = RedirectResponse(f"{settings.frontend_url}/dashboard")
    response.delete_cookie(OAUTH_STATE_COOKIE)
    await issue_session(db, response, user)
    return response
