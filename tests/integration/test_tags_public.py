import datetime as dt
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post
from app.tag.domain.entity import Tag

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


async def test_list_tags_count_desc_then_name_asc(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    aaa = Tag(name="aaa")
    bbb = Tag(name="bbb")
    ccc = Tag(name="ccc")
    p1 = make_post(id="p1")
    p2 = make_post(id="p2")
    p1.tags = [aaa, bbb]
    p2.tags = [bbb]
    await insert(aaa, bbb, ccc, p1, p2)
    items = (await client.get("/v1/tags")).json()
    assert [(it["name"], it["count"]) for it in items] == [
        ("bbb", 2),
        ("aaa", 1),
        ("ccc", 0),
    ]


async def test_list_tags_ignores_draft_posts(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    t = Tag(name="t")
    pub = make_post(id="pub", status="published")
    dft = make_post(id="dft", status="draft")
    pub.tags = [t]
    dft.tags = [t]
    await insert(t, pub, dft)
    items = (await client.get("/v1/tags")).json()
    assert items[0]["count"] == 1


async def test_tag_detail(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    t = Tag(name="t")
    p1 = make_post(id="p1", date=dt.date(2026, 2, 1))
    p2 = make_post(id="p2", date=dt.date(2026, 3, 1))
    p1.tags = [t]
    p2.tags = [t]
    await insert(t, p1, p2)
    body = (await client.get("/v1/tags/t")).json()
    assert body["tag"] == {"name": "t", "count": 2}
    assert [p["id"] for p in body["posts"]] == ["p2", "p1"]


async def test_tag_detail_404(client: AsyncClient) -> None:
    r = await client.get("/v1/tags/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TAG_NOT_FOUND"
