"""WebSocket: real-time agent progress for one project."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.api.deps import resolve_user
from app.core.db import get_session_factory
from app.core.security import ACCESS_COOKIE
from app.models import Project
from app.services.progress import hub

router = APIRouter()


@router.websocket("/ws/projects/{project_id}")
async def project_events(websocket: WebSocket, project_id: str) -> None:
    # Browsers send cookies with the WebSocket handshake, so the same access cookie authenticates it.
    token = websocket.cookies.get(ACCESS_COOKIE) or websocket.query_params.get("token")
    async with get_session_factory()() as db:
        try:
            user = await resolve_user(db, token)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        project = await db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()
    queue = hub.subscribe(project_id)
    try:
        await websocket.send_json({"type": "subscribed", "projectId": project_id})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(project_id, queue)
