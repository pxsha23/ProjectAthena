"""Export: zip download and push to a new GitHub repository."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, OwnedProject
from app.core.security import TokenError, decrypt_secret
from app.models import ProjectFile
from app.schemas.api import GithubExportIn, GithubExportOut, SearchHitOut
from app.services import embeddings, github
from app.services.export import build_zip, safe_slug
from app.services.pipeline import advance

router = APIRouter(prefix="/projects/{project_id}", tags=["export"])


async def _project_files(db: DbSession, project_id: str) -> list[ProjectFile]:
    files = list(
        await db.scalars(
            select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.path)
        )
    )
    if not files:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This project has no files yet")
    return files


@router.get("/export/zip")
async def export_zip(project: OwnedProject, db: DbSession) -> Response:
    files = await _project_files(db, project.id)
    slug = safe_slug(project.name)
    advance(project, "export")
    await db.commit()
    return Response(
        content=build_zip(files, slug),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


@router.post("/export/github", response_model=GithubExportOut)
async def export_github(
    body: GithubExportIn, project: OwnedProject, user: CurrentUser, db: DbSession
) -> GithubExportOut:
    if not user.github_token_encrypted:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Connect your GitHub account first (sign in with GitHub)"
        )
    try:
        token = decrypt_secret(user.github_token_encrypted)
    except TokenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Reconnect your GitHub account") from exc

    files = await _project_files(db, project.id)
    try:
        result = await github.push_to_new_repo(
            token, body.repo_name, files, private=body.private, description=project.description
        )
    except github.GitHubError as exc:
        code = status.HTTP_409_CONFLICT if exc.status_code == 422 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, detail=str(exc)) from exc

    advance(project, "export")
    await db.commit()
    return GithubExportOut(repo_url=result.repo_url, full_name=result.full_name, commit_sha=result.commit_sha)


@router.get("/search", response_model=list[SearchHitOut])
async def search_code(project: OwnedProject, db: DbSession, q: str, limit: int = 8) -> list[SearchHitOut]:
    """Semantic search over the project's code."""
    hits = await embeddings.search(db, project.id, q, limit=max(1, min(limit, 25)))
    return [SearchHitOut.model_validate(hit) for hit in hits]
