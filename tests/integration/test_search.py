import datetime as dt
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.post.domain.entity import Post

_Insert = Callable[..., Awaitable[None]]
_MakePost = Callable[..., Post]


async def test_missing_q_returns_422(client: AsyncClient) -> None:
    r = await client.get("/v1/search")
    assert r.status_code == 422


async def test_empty_q_returns_422(client: AsyncClient) -> None:
    # min_length=1 on Query — FastAPI/pydantic returns 422
    r = await client.get("/v1/search", params={"q": ""})
    assert r.status_code == 422


async def test_no_matches_returns_empty(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(make_post(id="a", title="spring boot", status="published"))
    r = await client.get("/v1/search", params={"q": "nothingmatchesthis"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_title_match_weighted_first(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    # "spring" in title (score 3) vs only in excerpt (score 2)
    await insert(
        make_post(
            id="title-match",
            title="spring framework",
            excerpt="unrelated",
            content="unrelated",
            date=dt.date(2026, 1, 1),
        ),
        make_post(
            id="excerpt-match",
            title="unrelated",
            excerpt="spring is nice",
            content="unrelated",
            date=dt.date(2026, 2, 1),
        ),
    )
    r = await client.get("/v1/search", params={"q": "spring"})
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()["items"]]
    assert ids[0] == "title-match"


async def test_korean_substring_match(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(
            id="korean-post",
            title="한국어 테스트 글",
            excerpt="한국어 substring 매칭 확인",
            content="내용",
        )
    )
    r = await client.get("/v1/search", params={"q": "한국어"})
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()["items"]]
    assert "korean-post" in ids


async def test_draft_not_returned(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    await insert(
        make_post(id="pub", title="spring boot", status="published"),
        make_post(id="dft", title="spring cloud", status="draft"),
    )
    r = await client.get("/v1/search", params={"q": "spring"})
    ids = [p["id"] for p in r.json()["items"]]
    assert "pub" in ids
    assert "dft" not in ids


async def test_pagination(
    client: AsyncClient,
    insert: _Insert,
    make_post: _MakePost,
) -> None:
    posts = [
        make_post(
            id=f"p{i:02d}", title=f"spring post {i}", date=dt.date(2026, 1, i + 1)
        )
        for i in range(5)
    ]
    await insert(*posts)
    r1 = await client.get("/v1/search", params={"q": "spring", "pageSize": 3, "page": 1})  # noqa: E501
    r2 = await client.get("/v1/search", params={"q": "spring", "pageSize": 3, "page": 2})  # noqa: E501
    assert r1.status_code == 200
    assert r2.status_code == 200
    b1 = r1.json()
    b2 = r2.json()
    assert b1["total"] == 5
    assert len(b1["items"]) == 3
    assert len(b2["items"]) == 2
    assert b1["hasNext"] is True
    assert b2["hasNext"] is False
