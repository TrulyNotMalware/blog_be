from contextvars import ContextVar, Token
from typing import Any

from sqlalchemy import ClauseElement, Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapper, Session


class Base(DeclarativeBase):
    pass


session_context: ContextVar[str] = ContextVar("session_context")

ENGINE_NAME: str = "default"
engines: dict[str, AsyncEngine] = {}


def get_session_context() -> str:
    return session_context.get()


def set_session_context(session_id: str) -> Token[str]:
    return session_context.set(session_id)


def reset_session_context(context: Token[str]) -> None:
    session_context.reset(context)


def init_engines(database_url: str, *, echo: bool = False) -> None:
    engines[ENGINE_NAME] = create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


async def dispose_engines() -> None:
    for engine in engines.values():
        await engine.dispose()
    engines.clear()


async def init_tables() -> None:
    engine = engines.get(ENGINE_NAME)
    if engine is None:
        raise RuntimeError("Engine not initialized. Call init_engines() first.")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


class _RoutedSession(Session):
    """Single-engine session class. Kept as a sync_session_class so a future
    read/write split only needs to override get_bind."""

    def get_bind(
        self,
        mapper: Mapper[Any] | None = None,  # noqa: ARG002
        clause: ClauseElement | None = None,  # noqa: ARG002
        **kw: Any,  # noqa: ARG002
    ) -> Engine:
        engine = engines.get(ENGINE_NAME)
        if engine is None:
            raise RuntimeError("Engine not initialized. Call init_engines() first.")
        return engine.sync_engine


async_session_factory = async_sessionmaker(
    class_=AsyncSession,
    sync_session_class=_RoutedSession,
    expire_on_commit=False,
)
session: async_scoped_session[AsyncSession] = async_scoped_session(
    session_factory=async_session_factory,
    scopefunc=get_session_context,
)


__all__ = [
    "Base",
    "async_session_factory",
    "dispose_engines",
    "engines",
    "get_session_context",
    "init_engines",
    "init_tables",
    "reset_session_context",
    "session",
    "session_context",
    "set_session_context",
]
