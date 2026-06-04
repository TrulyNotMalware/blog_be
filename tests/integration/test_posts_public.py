import datetime as dt
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post
from app.tag.domain.entity import Tag

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


async def test_list_empty(client: AsyncClient) -> None:
    r = await client.get("/v1/posts")
    assert r.status_code == 200
    assert r.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "pageSize": 10,
        "hasNext": False,
    }
    assert "public" in r.headers["cache-control"].lower()


async def test_list_orders_featured_then_date_desc(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="a", date=dt.date(2026, 1, 1), featured=False),
        make_post(id="b", date=dt.date(2026, 3, 1), featured=False),
        make_post(id="c", date=dt.date(2026, 2, 1), featured=True),
    )
    r = await client.get("/v1/posts")
    ids = [p["id"] for p in r.json()["items"]]
    assert ids == ["c", "b", "a"]


async def test_list_excludes_content_status_views(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="a", content="secret body"))
    item = r.json()["items"][0] if (r := await client.get("/v1/posts")) else None
    assert item is not None
    assert "content" not in item
    assert "status" not in item
    assert "views" not in item


async def test_list_camelcase_aliases(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="a", read_time="9분"))
    item = (await client.get("/v1/posts")).json()["items"][0]
    assert "readTime" in item
    assert "read_time" not in item


async def test_list_pagination(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        *[make_post(id=f"p{i:02d}", date=dt.date(2026, 1, i + 1)) for i in range(15)]
    )
    r = await client.get("/v1/posts", params={"page": 2, "pageSize": 10})
    body = r.json()
    assert body["page"] == 2
    assert body["pageSize"] == 10
    assert body["total"] == 15
    assert body["hasNext"] is False
    assert len(body["items"]) == 5


async def test_list_pagination_has_next(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        *[make_post(id=f"p{i:02d}", date=dt.date(2026, 1, i + 1)) for i in range(15)]
    )
    body = (await client.get("/v1/posts", params={"pageSize": 10})).json()
    assert body["hasNext"] is True


async def test_list_filter_by_tag(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    tag = Tag(name="filter-me")
    matched = make_post(id="match")
    matched.tags = [tag]
    other = make_post(id="other")
    await insert(tag, matched, other)
    r = await client.get("/v1/posts", params={"tag": "filter-me"})
    ids = [p["id"] for p in r.json()["items"]]
    assert ids == ["match"]


async def test_list_filter_by_kind(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="essay-1", kind="essay"),
        make_post(id="note-1", kind="note"),
    )
    r = await client.get("/v1/posts", params={"kind": "note"})
    ids = [p["id"] for p in r.json()["items"]]
    assert ids == ["note-1"]


async def test_list_excludes_non_published(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="pub", status="published"),
        make_post(id="dft", status="draft"),
        make_post(id="sch", status="scheduled"),
    )
    ids = [p["id"] for p in (await client.get("/v1/posts")).json()["items"]]
    assert ids == ["pub"]


async def test_detail_returns_content(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="x", content="full body"))
    body = (await client.get("/v1/posts/x")).json()
    assert body["id"] == "x"
    assert body["content"] == "full body"


async def test_detail_404(client: AsyncClient) -> None:
    r = await client.get("/v1/posts/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


async def test_detail_404_for_draft(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="dft", status="draft"))
    r = await client.get("/v1/posts/dft")
    assert r.status_code == 404
