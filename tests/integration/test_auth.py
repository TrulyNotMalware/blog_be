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


async def test_login_over_72_byte_password_is_401_not_500(client: AsyncClient) -> None:
    # bcrypt 5 raises ValueError for > 72 bytes; verify_password truncates so a
    # very long wrong password is a clean auth failure, never an unhandled 500.
    r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "a" * 200},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
