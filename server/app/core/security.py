"""Password hashing, JWT tokens, auth cookies and token encryption."""

import base64
import hashlib
import secrets
from datetime import timedelta
from typing import Literal

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Response

from app.core.config import get_settings
from app.core.db import utcnow

ACCESS_COOKIE = "athena_access"
REFRESH_COOKIE = "athena_refresh"
OAUTH_STATE_COOKIE = "athena_oauth_state"
REFRESH_COOKIE_PATH = "/api/auth"
ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Raised when a token is missing, expired, malformed or of the wrong type."""


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; pre-hash so long passwords are not silently truncated.
    digest = base64.b64encode(hashlib.sha256(password.encode()).digest())
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    digest = base64.b64encode(hashlib.sha256(password.encode()).digest())
    try:
        return bcrypt.checkpw(digest, password_hash.encode())
    except ValueError:
        return False


# ---------------------------------------------------------------- JWT


def create_token(user_id: str, token_type: TokenType, jti: str | None = None) -> tuple[str, str]:
    """Returns (token, jti)."""
    settings = get_settings()
    now = utcnow()
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    jti = jti or secrets.token_urlsafe(16)
    payload = {"sub": user_id, "type": token_type, "jti": jti, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), jti


def decode_token(token: str | None, expected_type: TokenType) -> dict:
    if not token:
        raise TokenError("Missing token")
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise TokenError("Wrong token type")
    return payload


# ---------------------------------------------------------------- cookies


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=settings.access_token_minutes * 60, path="/", **common
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_days * 86400,
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, domain=settings.cookie_domain)


# ---------------------------------------------------------------- encryption (GitHub tokens at rest)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise TokenError("Stored secret could not be decrypted") from exc


def hash_token_id(jti: str) -> str:
    return hashlib.sha256(jti.encode()).hexdigest()
