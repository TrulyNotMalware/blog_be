"""Token-version revocation + access/refresh rotation tests."""

from httpx import AsyncClient


async def _login(client: AsyncClient) -> tuple[str, str]:
    r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "test-admin-pw"},
    )
    assert r.status_code == 200
    body = r.json()
    return body["accessToken"], body["refreshToken"]


async def test_access_token_works_on_admin_endpoint(client: AsyncClient) -> None:
    access, _ = await _login(client)
    r = await client.get(
        "/v1/admin/posts", headers={"Authorization": f"Bearer {access}"}
    )
    assert r.status_code == 200


async def test_refresh_token_rejected_on_admin_endpoint(client: AsyncClient) -> None:
    """Refresh tokens must NOT grant API access — only /v1/auth/refresh accepts them."""
    _, refresh = await _login(client)
    r = await client.get(
        "/v1/admin/posts", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code == 401


async def test_access_token_rejected_on_refresh_endpoint(client: AsyncClient) -> None:
    """Access tokens must NOT be accepted on /v1/auth/refresh."""
    access, _ = await _login(client)
    r = await client.post("/v1/auth/refresh", json={"refreshToken": access})
    assert r.status_code == 401


async def test_refresh_rotates_both_tokens(client: AsyncClient) -> None:
    access1, refresh1 = await _login(client)
    r = await client.post("/v1/auth/refresh", json={"refreshToken": refresh1})
    assert r.status_code == 200
    body = r.json()
    access2 = body["accessToken"]
    refresh2 = body["refreshToken"]
    assert access2 != access1
    assert refresh2 != refresh1

    # New access token works.
    r2 = await client.get(
        "/v1/admin/posts", headers={"Authorization": f"Bearer {access2}"}
    )
    assert r2.status_code == 200


async def test_logout_revokes_both_tokens(client: AsyncClient) -> None:
    access, refresh = await _login(client)

    r_logout = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r_logout.status_code == 200

    # Old access token rejected.
    r_admin = await client.get(
        "/v1/admin/posts", headers={"Authorization": f"Bearer {access}"}
    )
    assert r_admin.status_code == 401

    # Old refresh token rejected.
    r_refresh = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    assert r_refresh.status_code == 401


async def test_fresh_login_after_logout_works(client: AsyncClient) -> None:
    old_access, _ = await _login(client)

    await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {old_access}"},
    )

    new_access, _ = await _login(client)
    assert new_access != old_access

    r = await client.get(
        "/v1/admin/posts", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert r.status_code == 200


async def test_no_token_returns_401(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/logout")
    assert r.status_code == 401


async def test_refresh_with_garbage_returns_401(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/refresh", json={"refreshToken": "not-a-jwt"})
    assert r.status_code == 401
