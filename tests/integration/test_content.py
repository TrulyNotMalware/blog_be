"""Integration tests for GET/PUT /v1/content/{key}."""

from httpx import AsyncClient


async def test_get_unknown_key_returns_404(client: AsyncClient) -> None:
    r = await client.get("/v1/content/about")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CONTENT_NOT_FOUND"


async def test_put_without_auth_returns_401(client: AsyncClient) -> None:
    r = await client.put("/v1/content/about", json={"content": {"text": "hello"}})
    assert r.status_code == 401


async def test_put_then_get_roundtrip(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    payload = {"content": {"title": "About", "body": "Hello world"}}
    put_r = await client.put("/v1/content/about", json=payload, headers=auth_headers)
    assert put_r.status_code == 200
    data = put_r.json()
    assert data["key"] == "about"
    assert data["content"] == payload["content"]
    assert "updatedAt" in data

    get_r = await client.get("/v1/content/about")
    assert get_r.status_code == 200
    assert get_r.json()["content"] == payload["content"]


async def test_put_updates_existing_content(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = {"content": {"v": 1}}
    r1 = await client.put("/v1/content/about", json=first, headers=auth_headers)
    assert r1.status_code == 200
    updated_at_1 = r1.json()["updatedAt"]

    second = {"content": {"v": 2}}
    r2 = await client.put("/v1/content/about", json=second, headers=auth_headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["content"] == {"v": 2}
    # updatedAt must be >= first (may be equal within same transaction second)
    assert body2["updatedAt"] >= updated_at_1


async def test_invalid_key_returns_422(client: AsyncClient) -> None:
    r = await client.get("/v1/content/INVALID_KEY!")
    assert r.status_code == 422


async def test_oversized_content_returns_422(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Build a content dict whose JSON serialisation exceeds 64 KB
    big = {"data": "x" * (64 * 1024 + 1)}
    r = await client.put(
        "/v1/content/about", json={"content": big}, headers=auth_headers
    )
    assert r.status_code == 422


async def test_non_dict_content_returns_422(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.put(
        "/v1/content/about",
        json={"content": ["not", "a", "dict"]},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_cache_control_on_get(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.put(
        "/v1/content/about",
        json={"content": {"x": 1}},
        headers=auth_headers,
    )
    r = await client.get("/v1/content/about")
    assert r.status_code == 200
    cc = r.headers.get("cache-control", "")
    assert "public" in cc
    assert "max-age=60" in cc
