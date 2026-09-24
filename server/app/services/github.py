"""GitHub API calls: OAuth code exchange, user lookup and pushing a project to a new repository."""

from collections.abc import Iterable
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.models import ProjectFile


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GitHubUser:
    id: int
    login: str
    name: str | None
    email: str | None


def _client(token: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        base_url=get_settings().github_api_url, headers=headers, timeout=30, transport=transport
    )


def _raise_for(response: httpx.Response, action: str) -> None:
    if response.is_error:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise GitHubError(f"GitHub could not {action}: {detail}", response.status_code)


async def exchange_code(code: str, transport: httpx.AsyncBaseTransport | None = None) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30, transport=transport) as client:
        response = await client.post(
            f"{settings.github_oauth_url}/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
    _raise_for(response, "exchange the login code")
    token = response.json().get("access_token")
    if not token:
        raise GitHubError(
            f"GitHub did not return a token: {response.json().get('error_description', 'unknown')}"
        )
    return token


async def fetch_user(token: str, transport: httpx.AsyncBaseTransport | None = None) -> GitHubUser:
    async with _client(token, transport) as client:
        response = await client.get("/user")
        _raise_for(response, "load your profile")
        data = response.json()
        email = data.get("email")
        if not email:
            emails = await client.get("/user/emails")
            if emails.is_success:
                primary = next((e for e in emails.json() if e.get("primary") and e.get("verified")), None)
                email = primary["email"] if primary else None
    return GitHubUser(id=data["id"], login=data["login"], name=data.get("name"), email=email)


@dataclass
class PushResult:
    repo_url: str
    full_name: str
    commit_sha: str


async def push_to_new_repo(
    token: str,
    repo_name: str,
    files: Iterable[ProjectFile],
    *,
    private: bool = True,
    description: str = "",
    transport: httpx.AsyncBaseTransport | None = None,
) -> PushResult:
    """Creates a repository and pushes every file as a single commit on main."""
    async with _client(token, transport) as client:
        response = await client.post(
            "/user/repos",
            json={"name": repo_name, "private": private, "description": description[:350], "auto_init": True},
        )
        _raise_for(response, f"create the repository '{repo_name}'")
        repo = response.json()
        full_name, branch = repo["full_name"], repo.get("default_branch") or "main"

        ref = await client.get(f"/repos/{full_name}/git/ref/heads/{branch}")
        _raise_for(ref, "read the new repository")
        parent_sha = ref.json()["object"]["sha"]

        tree = await client.post(
            f"/repos/{full_name}/git/trees",
            json={
                "tree": [
                    {"path": f.path, "mode": "100644", "type": "blob", "content": f.content} for f in files
                ]
            },
        )
        _raise_for(tree, "upload the files")

        commit = await client.post(
            f"/repos/{full_name}/git/commits",
            json={
                "message": "Initial commit from Athena",
                "tree": tree.json()["sha"],
                "parents": [parent_sha],
            },
        )
        _raise_for(commit, "create the commit")
        commit_sha = commit.json()["sha"]

        update = await client.patch(
            f"/repos/{full_name}/git/refs/heads/{branch}", json={"sha": commit_sha, "force": True}
        )
        _raise_for(update, "update the main branch")

    return PushResult(repo_url=repo["html_url"], full_name=full_name, commit_sha=commit_sha)
