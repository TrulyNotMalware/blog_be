"""Refresh-token rotation + reuse-detection tests.

Mirrors tests/integration/test_token_version.py. These exercise the
rotating-jti token family: each /refresh rotates the jti, a replayed (already
rotated) token revokes the whole family, logout revokes outstanding tokens, and
expired active rows are rejected.
"""

import datetime as dt
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select, update

from app.admin.domain.refresh_token import RefreshToken
from app.core.db.session import (
    reset_session_context,
    session,
    set_session_context,
)


async def _login(client: AsyncClient) -> tuple[str, str]:
    r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "test-admin-pw"},
    )
    assert r.status_code == 200
    body = r.json()
    return body["accessToken"], body["refreshToken"]


async def _refresh(
    client: AsyncClient, refresh: str
) -> tuple[int, dict[str, str]]:
    r = await client.post("/v1/auth/refresh", json={"refreshToken": refresh})
    body = r.json() if r.content else {}
    return r.status_code, body


async def _statuses() -> dict[str, str]:
    """Snapshot every refresh_tokens row's status keyed by jti."""
    sid = str(uuid4())
    ctx = set_session_context(sid)
    try:
        async with session.begin():
            result = await session.execute(
                select(RefreshToken.jti, RefreshToken.status)
            )
            return {row.jti: row.status for row in result.all()}
    finally:
        await session.remove()
        reset_session_context(ctx)


async def _expire_active_rows() -> None:
    """Force all active refresh rows to be already-expired."""
    sid = str(uuid4())
    ctx = set_session_context(sid)
    past = dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=1)
    try:
        async with session.begin():
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.status == "active")
                .values(expires_at=past)
            )
    finally:
        await session.remove()
        reset_session_context(ctx)


async def test_refresh_chain_rotates(client: AsyncClient) -> None:
    _, refresh1 = await _login(client)

    code1, body1 = await _refresh(client, refresh1)
    assert code1 == 200
    refresh2 = body1["refreshToken"]
    assert refresh2 != refresh1

    code2, body2 = await _refresh(client, refresh2)
    assert code2 == 200
    refresh3 = body2["refreshToken"]
    assert refresh3 != refresh2

    # Chain rotated through 3 distinct refresh tokens; only the latest is active.
    statuses = await _statuses()
    assert sorted(statuses.values()) == ["active", "rotated", "rotated"]


async def test_replayed_rotated_token_revokes_family(client: AsyncClient) -> None:
    _, refresh1 = await _login(client)

    code1, body1 = await _refresh(client, refresh1)
    assert code1 == 200
    refresh2 = body1["refreshToken"]

    # Replay refresh1 (now `rotated`) — reuse detection must fire.
    code_replay, _ = await _refresh(client, refresh1)
    assert code_replay == 401

    # Family revoked: even the legitimately-latest refresh2 is now rejected
    # (token_version was bumped, killing the whole family).
    code_latest, _ = await _refresh(client, refresh2)
    assert code_latest == 401

    statuses = await _statuses()
    assert set(statuses.values()) == {"revoked"}


async def test_logout_revokes_outstanding_refresh_tokens(
    client: AsyncClient,
) -> None:
    access, refresh = await _login(client)

    r_logout = await client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r_logout.status_code == 200

    code, _ = await _refresh(client, refresh)
    assert code == 401

    statuses = await _statuses()
    assert set(statuses.values()) == {"revoked"}


async def test_expired_active_jti_rejected(client: AsyncClient) -> None:
    _, refresh = await _login(client)

    # JWT exp is 7 days out, but the persisted active row is forced to the past.
    await _expire_active_rows()

    code, _ = await _refresh(client, refresh)
    assert code == 401
