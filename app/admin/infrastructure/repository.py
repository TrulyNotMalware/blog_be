import datetime as dt
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.admin.domain.entity import Admin
from app.admin.domain.refresh_token import RefreshToken
from app.core.db.session import (
    reset_session_context,
    session,
    set_session_context,
)


async def get_admin(username: str) -> Admin | None:
    result = await session.execute(select(Admin).where(Admin.username == username))
    return result.scalar_one_or_none()


async def upsert_admin(username: str, password_hash: str) -> Admin:
    """Insert admin row if not present. Returns the current row.

    Uses Postgres ON CONFLICT DO NOTHING so concurrent first-login requests
    don't race into a PK conflict between SELECT and INSERT.
    """
    stmt = (
        pg_insert(Admin)
        .values(username=username, password_hash=password_hash)
        .on_conflict_do_nothing(index_elements=["username"])
    )
    await session.execute(stmt)
    await session.flush()
    admin = await get_admin(username)
    assert admin is not None
    return admin


async def increment_token_version(username: str) -> int:
    """Bump token_version by 1. Returns the new version."""
    await session.execute(
        update(Admin)
        .where(Admin.username == username)
        .values(token_version=Admin.token_version + 1)
    )
    await session.flush()
    admin = await get_admin(username)
    assert admin is not None
    return admin.token_version


async def record_refresh_token(
    jti: str, subject: str, expires_at: dt.datetime
) -> None:
    """Persist a freshly issued refresh token as `active`."""
    await session.execute(
        pg_insert(RefreshToken).values(
            jti=jti, subject=subject, status="active", expires_at=expires_at
        )
    )
    await session.flush()


async def get_refresh_token(jti: str) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    return result.scalar_one_or_none()


async def mark_refresh_token_rotated(jti: str) -> None:
    await session.execute(
        update(RefreshToken).where(RefreshToken.jti == jti).values(status="rotated")
    )
    await session.flush()


async def revoke_refresh_tokens(subject: str) -> None:
    """Mark every one of the subject's refresh tokens `revoked` (family kill)."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.subject == subject)
        .values(status="revoked")
    )
    await session.flush()


async def revoke_family_committed(subject: str) -> None:
    """Bump token_version + revoke all refresh tokens in an INDEPENDENT committed
    transaction.

    Reuse detection performs this and then raises 401. Doing the writes in the
    request's ambient `@Transactional()` would be rolled back by that raise, so
    the family kill must commit on its own session scope (a fresh connection;
    the caller's transaction only ran SELECTs, so no lock contention)."""
    sid = str(uuid4())
    ctx = set_session_context(sid)
    try:
        async with session.begin():
            await session.execute(
                update(Admin)
                .where(Admin.username == subject)
                .values(token_version=Admin.token_version + 1)
            )
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.subject == subject)
                .values(status="revoked")
            )
    finally:
        await session.remove()
        reset_session_context(ctx)
