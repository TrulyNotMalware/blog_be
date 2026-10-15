"""The engine applies the configured pool size and server-side timeouts."""

from sqlalchemy import text
from sqlalchemy.pool import QueuePool

from app.core.config.config import loader
from app.core.db.session import ENGINE_NAME, engines


def test_engine_uses_configured_pool_size() -> None:
    cfg = loader.config
    pool = engines[ENGINE_NAME].pool
    assert isinstance(pool, QueuePool)
    assert pool.size() == cfg.DB_POOL_SIZE
    assert pool._max_overflow == cfg.DB_MAX_OVERFLOW  # no public accessor


async def test_connections_carry_server_side_timeouts() -> None:
    cfg = loader.config
    async with engines[ENGINE_NAME].connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT name, setting FROM pg_settings WHERE name IN "
                    "('statement_timeout', 'lock_timeout', "
                    "'idle_in_transaction_session_timeout')"
                )
            )
        ).all()
    assert dict(rows) == {
        "statement_timeout": str(cfg.DB_STATEMENT_TIMEOUT_MS),
        "lock_timeout": str(cfg.DB_LOCK_TIMEOUT_MS),
        "idle_in_transaction_session_timeout": str(
            cfg.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS
        ),
    }
