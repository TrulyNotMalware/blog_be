"""Integration tests for GET /v1/admin/posts and GET /v1/admin/posts/{id}."""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


# ---------------------------------------------------------------------------
# GET /v1/admin/posts — auth guard
# ---------------------------------------------------------------------------


async def test_list_admin_posts_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/v1/admin/posts")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/admin/posts — drafts AND published both returned
# ---------------------------------------------------------------------------


async def test_list_admin_posts_includes_drafts_and_published(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="pub-post", status="published"),
        make_post(id="draft-post", status="draft"),
    )
    r = await client.get("/v1/admin/posts", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert "pub-post" in ids
    assert "draft-post" in ids


# ---------------------------------------------------------------------------
# GET /v1/admin/posts?status= filters
# ---------------------------------------------------------------------------


async def test_list_admin_posts_filter_status_draft(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="d1", status="draft"),
        make_post(id="p1", status="published"),
    )
    r = await client.get("/v1/admin/posts?status=draft", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert all(item["status"] == "draft" for item in body["items"])
    ids = {item["id"] for item in body["items"]}
    assert "d1" in ids
    assert "p1" not in ids


async def test_list_admin_posts_filter_status_scheduled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="sched1", status="scheduled"),
        make_post(id="pub1", status="published"),
    )
    r = await client.get("/v1/admin/posts?status=scheduled", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert all(item["status"] == "scheduled" for item in body["items"])
    ids = {item["id"] for item in body["items"]}
    assert "sched1" in ids
    assert "pub1" not in ids


async def test_list_admin_posts_filter_status_published(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="pub1", status="published"),
        make_post(id="draft1", status="draft"),
    )
    r = await client.get("/v1/admin/posts?status=published", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert all(item["status"] == "published" for item in body["items"])
    ids = {item["id"] for item in body["items"]}
    assert "pub1" in ids
    assert "draft1" not in ids


# ---------------------------------------------------------------------------
# GET /v1/admin/posts?tag= filter (works with drafts too)
# ---------------------------------------------------------------------------


async def test_list_admin_posts_filter_tag(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    from app.tag.domain.entity import Tag

    foo_tag = Tag(name="foo")
    draft_with_tag = make_post(id="draft-tagged", status="draft")
    pub_no_tag = make_post(id="pub-no-tag", status="published")

    await insert(foo_tag)
    draft_with_tag.tags = [foo_tag]
    await insert(draft_with_tag, pub_no_tag)

    r = await client.get("/v1/admin/posts?tag=foo", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert "draft-tagged" in ids
    assert "pub-no-tag" not in ids


# ---------------------------------------------------------------------------
# GET /v1/admin/posts?kind= filter
# ---------------------------------------------------------------------------


async def test_list_admin_posts_filter_kind(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="note1", kind="note"),
        make_post(id="essay1", kind="essay"),
    )
    r = await client.get("/v1/admin/posts?kind=note", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert all(item["kind"] == "note" for item in body["items"])
    ids = {item["id"] for item in body["items"]}
    assert "note1" in ids
    assert "essay1" not in ids


# ---------------------------------------------------------------------------
# GET /v1/admin/posts pagination
# ---------------------------------------------------------------------------


async def test_list_admin_posts_pagination(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    posts = [make_post(id=f"post-{i}", status="draft") for i in range(5)]
    await insert(*posts)

    # page 1, pageSize=3 → hasNext=True, total=5
    r = await client.get("/v1/admin/posts?page=1&pageSize=3", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["pageSize"] == 3
    assert body["hasNext"] is True
    assert len(body["items"]) == 3

    # page 2, pageSize=3 → hasNext=False
    r2 = await client.get("/v1/admin/posts?page=2&pageSize=3", headers=auth_headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["page"] == 2
    assert body2["hasNext"] is False
    assert len(body2["items"]) == 2


# ---------------------------------------------------------------------------
# GET /v1/admin/posts/{id} — auth guard
# ---------------------------------------------------------------------------


async def test_get_admin_post_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/v1/admin/posts/any-id")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/admin/posts/{id} — draft returns full PostAdmin shape
# ---------------------------------------------------------------------------


async def test_get_admin_post_draft_returns_full_shape(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(
            id="draft-detail",
            title="Draft Detail",
            content="full body",
            status="draft",
            views=7,
        )
    )
    r = await client.get("/v1/admin/posts/draft-detail", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "draft-detail"
    assert body["status"] == "draft"
    assert body["content"] == "full body"
    assert body["views"] == 7
    # camelCase timestamp fields must be present
    assert "createdAt" in body
    assert "updatedAt" in body


# ---------------------------------------------------------------------------
# GET /v1/admin/posts/{id} — non-existent → 404 POST_NOT_FOUND
# ---------------------------------------------------------------------------


async def test_get_admin_post_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r = await client.get("/v1/admin/posts/does-not-exist", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


# ---------------------------------------------------------------------------
# Response shape is camelCase (alias check)
# ---------------------------------------------------------------------------


async def test_list_admin_posts_response_is_camelcase(
    client: AsyncClient,
    auth_headers: dict[str, str],
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="camel-check", status="draft"))
    r = await client.get("/v1/admin/posts?pageSize=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # Pagination envelope
    assert "pageSize" in body
    assert "hasNext" in body
    # Per-item admin fields
    item = body["items"][0]
    assert "createdAt" in item
    assert "updatedAt" in item
    assert "readTime" in item
