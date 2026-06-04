from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.admin.domain.entity import Admin
from app.core.db.session import session


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
