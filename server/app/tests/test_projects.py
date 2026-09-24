import httpx

from app.tests.conftest import IDEA, _client, create_project, register


async def test_create_list_update_delete(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    assert project["stage"] == "idea"
    assert project["status"] == "draft"
    assert project["specReady"] is False
    assert project["stack"] == []

    listed = (await auth_client.get("/api/projects")).json()
    assert [p["id"] for p in listed] == [project["id"]]

    updated = await auth_client.patch(
        f"/api/projects/{project['id']}", json={"starred": True, "name": "Renamed"}
    )
    assert updated.status_code == 200
    assert updated.json()["starred"] is True and updated.json()["name"] == "Renamed"

    # The idea becomes the first chat message.
    messages = (await auth_client.get(f"/api/projects/{project['id']}/messages")).json()
    assert messages[0]["role"] == "user" and messages[0]["content"] == IDEA

    assert (await auth_client.delete(f"/api/projects/{project['id']}")).status_code == 204
    assert (await auth_client.get(f"/api/projects/{project['id']}")).status_code == 404


async def test_idea_must_be_meaningful(auth_client: httpx.AsyncClient) -> None:
    response = await auth_client.post("/api/projects", json={"name": "X", "idea": "too short"})
    assert response.status_code == 422


async def test_projects_are_private(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    async with _client() as other:
        await register(other, name="Someone Else")
        assert (await other.get(f"/api/projects/{project['id']}")).status_code == 404
        assert (await other.get(f"/api/projects/{project['id']}/files")).status_code == 404
        assert (await other.post(f"/api/projects/{project['id']}/stages/idea/run")).status_code == 404
        assert (await other.get("/api/projects")).json() == []


async def test_file_crud_and_path_safety(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    base = f"/api/projects/{project['id']}/files"

    saved = await auth_client.put(f"{base}/backend/app.py", json={"content": "print('hi')\n"})
    assert saved.status_code == 200
    assert saved.json()["language"] == "python"
    assert saved.json()["source"] == "user"

    assert (await auth_client.get(f"{base}/backend/app.py")).json()["content"] == "print('hi')\n"
    assert [f["path"] for f in (await auth_client.get(base)).json()] == ["backend/app.py"]

    assert (await auth_client.put(f"{base}/../escape.py", json={"content": "x"})).status_code in (400, 404)
    assert (await auth_client.put(f"{base}/a/../../escape.py", json={"content": "x"})).status_code in (
        400,
        404,
    )

    assert (await auth_client.delete(f"{base}/backend/app.py")).status_code == 204
    assert (await auth_client.get(f"{base}/backend/app.py")).status_code == 404
