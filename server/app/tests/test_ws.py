"""WebSocket progress events. Uses Starlette's sync TestClient, which runs the app on its own event loop."""

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core import db as db_module
from app.main import app
from app.services.progress import ProgressHub


@pytest.fixture
def sync_client():
    # The async tests share an engine bound to pytest's event loop; give TestClient its own.
    saved = db_module._engine, db_module._session_factory
    db_module._engine = db_module._session_factory = None
    try:
        with TestClient(app) as client:  # lifespan disposes the engine it created
            yield client
    finally:
        db_module._engine, db_module._session_factory = saved


def test_stage_progress_is_streamed(sync_client: TestClient) -> None:
    email = f"ws-{uuid.uuid4().hex[:8]}@example.com"
    assert (
        sync_client.post(
            "/api/auth/register", json={"name": "WS", "email": email, "password": "long-enough-pw"}
        ).status_code
        == 201
    )
    project = sync_client.post(
        "/api/projects", json={"name": "Live", "idea": "An app that shows live progress."}
    ).json()

    with sync_client.websocket_connect(f"/api/ws/projects/{project['id']}") as ws:
        assert ws.receive_json()["type"] == "subscribed"
        assert sync_client.post(f"/api/projects/{project['id']}/stages/idea/run").status_code == 202
        events = []
        while not events or events[-1]["type"] not in ("stage_completed", "stage_failed"):
            events.append(ws.receive_json())

    types = [e["type"] for e in events]
    assert types == [
        "stage_started",
        "agent_started",
        "agent_succeeded",
        "checks_completed",
        "stage_completed",
    ]
    assert events[2]["agent"] == "idea" and events[2]["retries"] == 0
    assert events[3] == {**events[3], "passed": 2, "total": 2, "failed": []}


def test_websocket_rejects_strangers(sync_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), sync_client.websocket_connect("/api/ws/projects/whatever") as ws:
        ws.receive_json()


async def test_hub_delivers_only_to_subscribers_of_that_project() -> None:
    hub = ProgressHub()
    a, b = hub.subscribe("p1"), hub.subscribe("p2")
    await hub.publish("p1", "stage_started", stage="idea")
    assert (await a.get())["stage"] == "idea"
    assert b.empty()
    hub.unsubscribe("p1", a)
    await hub.publish("p1", "stage_started")  # no subscribers left: must not raise
