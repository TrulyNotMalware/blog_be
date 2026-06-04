from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


_BASE_PAYLOAD = {
    "title": "Hello world",
    "excerpt": "x",
    "tags": [],
    "date": "2026-05-01",
    "readTime": "1분",
    "kind": "note",
}


async def test_create_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/v1/posts", json=_BASE_PAYLOAD)
    assert r.status_code == 401


async def test_create_auto_slugifies_title(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r = await client.post("/v1/posts", json=_BASE_PAYLOAD, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == "hello-world"
    assert body["status"] == "draft"
    assert body["tags"] == []


async def test_create_with_explicit_id_and_tags(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {**_BASE_PAYLOAD, "id": "custom-slug", "tags": ["a", "b"]}
    body = (await client.post("/v1/posts", json=payload, headers=auth_headers)).json()
    assert body["id"] == "custom-slug"
    assert sorted(body["tags"]) == ["a", "b"]


async def test_create_slug_conflict_409(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="dup"))
    payload = {**_BASE_PAYLOAD, "id": "dup"}
    r = await client.post("/v1/posts", json=payload, headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SLUG_CONFLICT"


async def test_patch_partial_update(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="x", title="Old"))
    r = await client.patch(
        "/v1/posts/x", json={"title": "New"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New"


async def test_patch_replaces_tags(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="x"))
    r = await client.patch(
        "/v1/posts/x",
        json={"tags": ["alpha", "beta"]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert sorted(r.json()["tags"]) == ["alpha", "beta"]


async def test_patch_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r = await client.patch(
        "/v1/posts/nope", json={"title": "x"}, headers=auth_headers
    )
    assert r.status_code == 404


async def test_delete_then_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="x"))
    assert (await client.delete("/v1/posts/x", headers=auth_headers)).status_code == 204
    second = await client.delete("/v1/posts/x", headers=auth_headers)
    assert second.status_code == 404


async def test_publish_transitions_status(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="x", status="draft"))
    body = (
        await client.post("/v1/posts/x/publish", headers=auth_headers)
    ).json()
    assert body["status"] == "published"


async def test_admin_response_includes_admin_only_fields(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = (
        await client.post("/v1/posts", json=_BASE_PAYLOAD, headers=auth_headers)
    ).json()
    for key in ("status", "views", "createdAt", "updatedAt"):
        assert key in body, f"missing admin field {key}"
