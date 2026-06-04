from httpx import AsyncClient


async def test_error_envelope_shape(client: AsyncClient) -> None:
    r = await client.get("/v1/posts/nope")
    assert r.status_code == 404
    body = r.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) >= {"code", "message"}
    assert isinstance(body["error"]["code"], str)
    assert isinstance(body["error"]["message"], str)


async def test_validation_error_envelope(client: AsyncClient) -> None:
    # pageSize > 100 violates the Query(le=100) constraint
    r = await client.get("/v1/posts", params={"pageSize": 101})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]


async def test_admin_endpoint_without_token_401(client: AsyncClient) -> None:
    r = await client.delete("/v1/posts/x")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_admin_endpoint_with_bad_token_401(client: AsyncClient) -> None:
    r = await client.delete(
        "/v1/posts/x",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert r.status_code == 401
