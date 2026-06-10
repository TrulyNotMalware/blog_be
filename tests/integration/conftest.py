"""Fixtures for DB-backed integration tests.

Auto-applies the `integration` marker to everything in this package. Skipping
when `TEST_DATABASE_URL` is unset is handled in `tests/conftest.py`.
"""

import datetime as dt
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Side-effect imports — register ORM mappings on Base.metadata.
import app.admin.domain.entity
import app.admin.domain.refresh_token
import app.content.domain.entity
import app.post.domain.entity
import app.tag.domain.entity  # noqa: F401
from api.root_router import root_router
from app.admin.domain.entity import Admin
from app.core.config.config import loader
from app.core.db.session import (
    ENGINE_NAME,
    Base,
    dispose_engines,
    engines,
    init_engines,
    init_tables,
    reset_session_context,
    session,
    set_session_context,
)
from app.core.exception.error_base import CustomException
from app.core.exception.exception_handlers import (
    custom_exception_handler,
    validation_exception_handler,
)
from app.core.fastapi.middlewares.sqlalchemy import SQLAlchemyMiddleware
from app.core.security.password import hash_password
from app.post.domain.entity import Post
from app.tag.domain.entity import Tag

pytestmark = pytest.mark.integration

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "test-admin-pw"


@pytest.fixture(scope="session", autouse=True)
async def _db_engine() -> AsyncIterator[None]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)
    init_engines(database_url=url)
    await init_tables()
    yield
    await dispose_engines()


@pytest.fixture(scope="session")
def _admin_password_hash() -> str:
    return hash_password(TEST_ADMIN_PASSWORD)


@pytest.fixture(autouse=True)
def _patch_auth_config(
    monkeypatch: pytest.MonkeyPatch,
    _admin_password_hash: str,
) -> None:
    # JWT_PRIVATE_KEY_PEM + JWT_KID are patched by the root tests/conftest.py
    # autouse fixture; only patch admin identity bits here.
    cfg = loader.config
    monkeypatch.setattr(cfg, "ADMIN_USERNAME", TEST_ADMIN_USERNAME)
    monkeypatch.setattr(cfg, "ADMIN_PASSWORD_HASH", _admin_password_hash)


@pytest.fixture(autouse=True)
async def _clean_and_seed(
    _admin_password_hash: str,
) -> None:
    """Truncate all tables then seed the admin row for every test."""
    engine = engines[ENGINE_NAME]
    table_names = [t.name for t in Base.metadata.sorted_tables]
    joined = ", ".join(f'"{n}"' for n in table_names)
    if joined:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")
            )
    sid = str(uuid4())
    ctx = set_session_context(sid)
    try:
        async with session.begin():
            session.add(
                Admin(username=TEST_ADMIN_USERNAME, password_hash=_admin_password_hash)
            )
    finally:
        await session.remove()
        reset_session_context(ctx)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Full app stack (CORS + SQLAlchemyMiddleware) without lifespan —
    engine is owned by the session fixture, not the app."""
    application = FastAPI(
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(SQLAlchemyMiddleware),
        ],
    )
    application.include_router(root_router)
    application.add_exception_handler(CustomException, custom_exception_handler)
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Returns an access token. Use this for admin endpoint requests."""
    r = await client.post(
        "/v1/auth/login",
        json={
            "username": TEST_ADMIN_USERNAME,
            "password": TEST_ADMIN_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    return str(r.json()["accessToken"])


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


_InsertFn = Callable[..., Awaitable[None]]


@pytest.fixture
def insert() -> _InsertFn:
    """Persist ORM objects in their own committed transaction.

    Uses a temporary session scope so the data is durable when the HTTP client
    later issues a request that opens its own per-request session.
    """

    async def _insert(*objects: object) -> None:
        sid = str(uuid4())
        ctx = set_session_context(sid)
        try:
            async with session.begin():
                for obj in objects:
                    session.add(obj)
        finally:
            await session.remove()
            reset_session_context(ctx)

    return _insert


@pytest.fixture
def make_post() -> Callable[..., Post]:
    def _make(**overrides: object) -> Post:
        defaults: dict[str, object] = {
            "id": "test-post",
            "title": "Test",
            "excerpt": "test excerpt",
            "content": "body",
            "date": dt.date(2026, 5, 1),
            "read_time": "1분",
            "kind": "essay",
            "status": "published",
            "featured": False,
            "views": 0,
        }
        defaults.update(overrides)
        return Post(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_tag() -> Callable[..., Tag]:
    def _make(name: str = "testtag") -> Tag:
        return Tag(name=name)

    return _make
