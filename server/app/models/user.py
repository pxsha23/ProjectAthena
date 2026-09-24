import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TZDateTime, utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Null for accounts that only sign in with GitHub.
    password_hash: Mapped[str | None] = mapped_column(String(200))
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    github_login: Mapped[str | None] = mapped_column(String(100))
    # Fernet-encrypted OAuth token, needed to push exports to GitHub.
    github_token_encrypted: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """One row per issued refresh token, so tokens can be rotated and revoked."""

    __tablename__ = "refresh_tokens"

    # sha256 of the token's jti; the raw jti never touches the database.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime())
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
