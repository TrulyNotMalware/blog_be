"""Unit coverage for POST /v1/auth/login paths that never reach the database."""

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware import Middleware

import api.v1.auth as auth_api
from api.root_router import root_router
from app.core.exception.error_base import CustomException
from app.core.exception.exception_handlers import custom_exception_handler
from app.core.fastapi.middlewares.sqlalchemy import SQLAlchemyMiddleware
from app.server import LoginRateLimitMiddleware


def _app_with_session() -> FastAPI:
    app = FastAPI(middleware=[Middleware(SQLAlchemyMiddleware)])
    app.include_router(root_router)
    app.add_exception_handler(CustomException, custom_exception_handler)
    return app


async def test_login_verifies_password_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # bcrypt takes ~200 ms; on the loop it would stall every other request.
    on_loop: list[bool] = []

    def _verify(_password: str, _hashed: str) -> bool:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_loop.append(False)
        else:
            on_loop.append(True)
        return False

    monkeypatch.setattr(auth_api, "verify_password", _verify)
    transport = ASGITransport(app=_app_with_session())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/v1/auth/login", json={"username": "admin", "password": "x"})

    assert r.status_code == 401
    assert on_loop == [False]


async def test_rate_limit_ignores_client_supplied_forwarded_for() -> None:
    app = FastAPI(middleware=[Middleware(LoginRateLimitMiddleware, max_attempts=2)])

    @app.post("/v1/auth/login")
    async def _login() -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        codes = [
            (
                await c.post(
                    "/v1/auth/login", headers={"X-Forwarded-For": f"10.0.0.{i}"}
                )
            ).status_code
            for i in range(3)
        ]

    assert codes == [200, 200, 429]
