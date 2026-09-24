"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import ACCESS_COOKIE, TokenError, decode_token
from app.models import Project, User

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:]
    return None


async def resolve_user(db: AsyncSession, token: str | None) -> User:
    try:
        payload = decode_token(token, "access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = await db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


async def get_current_user(
    db: DbSession,
    access_cookie: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Accepts the httpOnly access cookie (browser) or an Authorization: Bearer header (scripts, tests)."""
    return await resolve_user(db, access_cookie or _bearer(authorization))


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_owned_project(project_id: str, db: DbSession, user: CurrentUser) -> Project:
    project = await db.get(Project, project_id)
    # 404 (not 403) so other users' project ids are not revealed.
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


OwnedProject = Annotated[Project, Depends(get_owned_project)]
