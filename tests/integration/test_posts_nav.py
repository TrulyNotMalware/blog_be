import datetime as dt
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


async def test_nav_first_post_has_no_next(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Newest post (highest date) has no next."""
    await insert(
        make_post(id="old", date=dt.date(2026, 1, 1)),
        make_post(id="new", date=dt.date(2026, 3, 1)),
    )
    r = await client.get("/v1/posts/new/nav")
    assert r.status_code == 200
    body = r.json()
    assert body["next"] is None
    assert body["prev"]["id"] == "old"


async def test_nav_last_post_has_no_prev(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Oldest post (lowest date) has no prev."""
    await insert(
        make_post(id="old", date=dt.date(2026, 1, 1)),
        make_post(id="new", date=dt.date(2026, 3, 1)),
    )
    r = await client.get("/v1/posts/old/nav")
    assert r.status_code == 200
    body = r.json()
    assert body["prev"] is None
    assert body["next"]["id"] == "new"


async def test_nav_middle_post_has_both(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Middle post has both prev and next."""
    await insert(
        make_post(id="a", date=dt.date(2026, 1, 1)),
        make_post(id="b", date=dt.date(2026, 2, 1)),
        make_post(id="c", date=dt.date(2026, 3, 1)),
    )
    r = await client.get("/v1/posts/b/nav")
    assert r.status_code == 200
    body = r.json()
    assert body["prev"]["id"] == "a"
    assert body["next"]["id"] == "c"


async def test_nav_draft_returns_404(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Draft post id → 404."""
    await insert(make_post(id="dft", status="draft"))
    r = await client.get("/v1/posts/dft/nav")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


async def test_nav_nonexistent_returns_404(client: AsyncClient) -> None:
    """Non-existent id → 404."""
    r = await client.get("/v1/posts/no-such-post/nav")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


async def test_nav_response_shape(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Response includes id, title, excerpt, date, tags (camelCase)."""
    await insert(
        make_post(id="a", date=dt.date(2026, 1, 1)),
        make_post(id="b", date=dt.date(2026, 2, 1)),
    )
    r = await client.get("/v1/posts/b/nav")
    assert r.status_code == 200
    prev = r.json()["prev"]
    assert "id" in prev
    assert "title" in prev
    assert "excerpt" in prev
    assert "date" in prev
    assert "tags" in prev
    # must not expose content or status
    assert "content" not in prev
    assert "status" not in prev


async def test_nav_draft_excluded_from_neighbors(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    """Draft posts are not returned as prev/next neighbors."""
    await insert(
        make_post(id="old", date=dt.date(2026, 1, 1)),
        make_post(id="dft", date=dt.date(2026, 2, 1), status="draft"),
        make_post(id="new", date=dt.date(2026, 3, 1)),
    )
    r = await client.get("/v1/posts/new/nav")
    assert r.status_code == 200
    body = r.json()
    # draft should be skipped; prev should be "old"
    assert body["prev"]["id"] == "old"
