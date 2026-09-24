from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import REFRESH_COOKIE, decrypt_secret
from app.models import User
from app.services import github
from app.tests.conftest import TEST_PASSWORD, register


async def test_register_sets_cookies_and_returns_user(client: httpx.AsyncClient) -> None:
    user = await register(client, name="Ada")
    assert user["name"] == "Ada"
    assert "passwordHash" not in user and "password_hash" not in user
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]


async def test_duplicate_email_is_rejected(client: httpx.AsyncClient) -> None:
    user = await register(client)
    again = await client.post(
        "/api/auth/register", json={"name": "Other", "email": user["email"], "password": TEST_PASSWORD}
    )
    assert again.status_code == 409


async def test_short_password_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "short"}
    )
    assert response.status_code == 422


async def test_login_checks_password(client: httpx.AsyncClient) -> None:
    user = await register(client)
    client.cookies.clear()
    bad = await client.post("/api/auth/login", json={"email": user["email"], "password": "wrong-password"})
    assert bad.status_code == 401
    good = await client.post(
        "/api/auth/login", json={"email": user["email"].upper(), "password": TEST_PASSWORD}
    )
    assert good.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_protected_routes_need_a_session(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/projects")).status_code == 401
    garbage = await client.get("/api/projects", headers={"Authorization": "Bearer not-a-token"})
    assert garbage.status_code == 401


async def test_refresh_rotates_and_detects_reuse(client: httpx.AsyncClient) -> None:
    await register(client)
    old_refresh = client.cookies.get(REFRESH_COOKIE, path="/api/auth")
    assert old_refresh

    rotated = await client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE, path="/api/auth")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the old (revoked) token fails and revokes the whole session family.
    async with httpx.AsyncClient(transport=client._transport, base_url="http://testserver") as attacker:
        attacker.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/auth")
        assert (await attacker.post("/api/auth/refresh")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_revokes_refresh_token(client: httpx.AsyncClient) -> None:
    await register(client)
    refresh = client.cookies.get(REFRESH_COOKIE, path="/api/auth")
    assert (await client.post("/api/auth/logout")).status_code == 204
    client.cookies.set(REFRESH_COOKIE, refresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_github_login_needs_configuration(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/providers")).json() == {"github": False}
    response = await client.get("/api/auth/github/login")
    assert response.status_code == 503


@pytest.fixture
def github_configured(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", "client-id")
    monkeypatch.setattr(settings, "github_client_secret", "client-secret")
    return settings


async def test_github_oauth_creates_user_and_stores_encrypted_token(
    client: httpx.AsyncClient, db, github_configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (await client.get("/api/auth/providers")).json() == {"github": True}
    start = await client.get("/api/auth/github/login")
    assert start.status_code == 307
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    async def fake_exchange(code: str) -> str:
        assert code == "the-code"
        return "gho_secret_token"

    async def fake_user(token: str) -> github.GitHubUser:
        return github.GitHubUser(id=4242, login="octo-student", name="Octo Student", email="octo@example.com")

    monkeypatch.setattr(github, "exchange_code", fake_exchange)
    monkeypatch.setattr(github, "fetch_user", fake_user)

    bad_state = await client.get("/api/auth/github/callback", params={"code": "the-code", "state": "forged"})
    assert "error=github_state" in bad_state.headers["location"]

    done = await client.get("/api/auth/github/callback", params={"code": "the-code", "state": state})
    assert done.status_code == 307
    assert done.headers["location"].endswith("/dashboard")

    me = (await client.get("/api/auth/me")).json()
    assert me["githubUsername"] == "octo-student"
    assert me["hasGithubToken"] is True

    user = await db.scalar(select(User).where(User.github_id == 4242))
    assert user.github_token_encrypted != "gho_secret_token"
    assert decrypt_secret(user.github_token_encrypted) == "gho_secret_token"
