from httpx import AsyncClient


async def test_login_success(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "test-admin-pw"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["accessToken"], str)
    assert isinstance(body["refreshToken"], str)
    assert body["accessToken"] != body["refreshToken"]


async def test_login_bad_password(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_login_unknown_user(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/login",
        json={"username": "nope", "password": "test-admin-pw"},
    )
    assert r.status_code == 401
