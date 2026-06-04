"""ENV-based auth branching — prod trusts headers, local verifies the JWT."""
from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware import Middleware

from app.core.config.config import Config, loader
from app.core.exception.error_base import CustomException
from app.core.exception.exception_handlers import custom_exception_handler
from app.core.security.auth import require_admin
from app.server import GatewaySharedSecretMiddleware
from tests.conftest import TEST_RSA_KID, TEST_RSA_PRIVATE_PEM


def _make_app(*, mw: list[Middleware] | None = None) -> FastAPI:
    app = FastAPI(middleware=mw or [])

    @app.get("/v1/admin/whoami")
    async def _route(
        subject: Annotated[str, Depends(require_admin)],
    ) -> dict[str, str]:
        return {"subject": subject}

    @app.get("/healthz")
    async def _hz() -> dict[str, str]:
        return {"status": "ok"}

    app.add_exception_handler(CustomException, custom_exception_handler)
    return app


@pytest.fixture
def restore_config():
    original = loader._config
    yield
    loader._config = original


@pytest.fixture
def prod_config(restore_config):  # noqa: ARG001 — fixture ordering
    loader._config = Config(
        ENV="prod",
        JWT_PRIVATE_KEY_PEM=TEST_RSA_PRIVATE_PEM,
        JWT_KID=TEST_RSA_KID,
        ADMIN_USERNAME="admin",
        GATEWAY_SHARED_SECRET="super-secret-gateway-token-32-chars-min-ok",
    )
    return loader._config


@pytest.fixture
def local_config(restore_config):  # noqa: ARG001 — fixture ordering
    loader._config = Config(ENV="local", ADMIN_USERNAME="admin")
    return loader._config


@pytest.mark.asyncio
async def test_prod_missing_x_user_id_returns_401(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={"X-Gateway-Auth": prod_config.GATEWAY_SHARED_SECRET},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_prod_mismatching_user_returns_403(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={
                "X-Gateway-Auth": prod_config.GATEWAY_SHARED_SECRET,
                "X-User-ID": "intruder",
            },
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_prod_valid_user_with_secret_passes(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={
                "X-Gateway-Auth": prod_config.GATEWAY_SHARED_SECRET,
                "X-User-ID": prod_config.ADMIN_USERNAME,
            },
        )
    assert r.status_code == 200
    assert r.json() == {"subject": prod_config.ADMIN_USERNAME}


@pytest.mark.asyncio
async def test_prod_request_without_gateway_secret_is_blocked(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={"X-User-ID": prod_config.ADMIN_USERNAME},
        )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "GATEWAY_HOP_MISSING"


@pytest.mark.asyncio
async def test_prod_wrong_gateway_secret_is_blocked(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={
                "X-Gateway-Auth": "wrong-secret",
                "X-User-ID": prod_config.ADMIN_USERNAME,
            },
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_prod_healthz_bypasses_gateway_check(prod_config) -> None:
    app = _make_app(
        mw=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_prod_jwks_endpoint_bypasses_gateway_check(prod_config) -> None:
    """The gateway's NimbusReactiveJwtDecoder fetches /.well-known/jwks.json
    directly (it does not flow through the gateway routing chain), so no
    `X-Gateway-Auth` is stamped on that call. The hop-proof middleware must
    let JWKS through, or every JWT verification breaks in prod.

    Mounts the real `root_router` (not a stub route) so wiring drift between
    the bypass list and the actual route path is caught here.
    """
    from api.root_router import root_router

    app = FastAPI(
        middleware=[
            Middleware(
                GatewaySharedSecretMiddleware,
                expected_secret=prod_config.GATEWAY_SHARED_SECRET,
            ),
        ],
    )
    app.include_router(root_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/.well-known/jwks.json")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("keys"), list)
    assert body["keys"][0]["kty"] == "RSA"


@pytest.mark.asyncio
async def test_local_x_user_id_only_returns_401(local_config) -> None:
    """Local mode rejects bare X-User-ID — requires an Authorization Bearer."""
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(
            "/v1/admin/whoami",
            headers={"X-User-ID": local_config.ADMIN_USERNAME},
        )
    assert r.status_code == 401


_PROD_OK_GATEWAY_SECRET = "super-secret-gateway-token-32-chars-min-ok"


def _prod_kwargs(**overrides: object) -> dict[str, object]:
    """Baseline kwargs that satisfy every prod validator."""
    base: dict[str, object] = {
        "JWT_PRIVATE_KEY_PEM": TEST_RSA_PRIVATE_PEM,
        "JWT_KID": TEST_RSA_KID,
        "GATEWAY_SHARED_SECRET": _PROD_OK_GATEWAY_SECRET,
    }
    base.update(overrides)
    return base


def test_config_is_prod_handles_both_aliases() -> None:
    """Both `prod` and `production` (any casing) must resolve to is_prod=True."""
    assert Config(ENV="prod", **_prod_kwargs()).is_prod is True
    assert Config(ENV="PROD", **_prod_kwargs()).is_prod is True
    assert Config(ENV="production", **_prod_kwargs()).is_prod is True
    assert Config(ENV="Production", **_prod_kwargs()).is_prod is True
    assert Config(ENV="local").is_prod is False
    assert Config(ENV="test").is_prod is False


def test_prod_requires_gateway_shared_secret() -> None:
    """Empty GATEWAY_SHARED_SECRET in prod must fail boot —
    otherwise the hop-proof middleware silently no-ops."""
    with pytest.raises(ValueError, match="GATEWAY_SHARED_SECRET"):
        Config(ENV="prod", **_prod_kwargs(GATEWAY_SHARED_SECRET=""))


def test_prod_rejects_short_gateway_shared_secret() -> None:
    with pytest.raises(ValueError, match="GATEWAY_SHARED_SECRET"):
        Config(ENV="prod", **_prod_kwargs(GATEWAY_SHARED_SECRET="too-short"))


def test_prod_rejects_garbage_pem() -> None:
    """Even PEM-shaped garbage must fail at boot, not at first login."""
    fake = "-----BEGIN PRIVATE KEY-----\nnot-actually-a-key\n-----END PRIVATE KEY-----"
    with pytest.raises(ValueError, match="valid PEM-encoded private key"):
        Config(ENV="prod", **_prod_kwargs(JWT_PRIVATE_KEY_PEM=fake))


def test_prod_requires_jwt_private_key() -> None:
    with pytest.raises(ValueError, match="JWT_PRIVATE_KEY_PEM"):
        Config(ENV="prod", **_prod_kwargs(JWT_PRIVATE_KEY_PEM=""))


def test_prod_requires_jwt_kid() -> None:
    with pytest.raises(ValueError, match="JWT_KID"):
        Config(ENV="prod", **_prod_kwargs(JWT_KID=""))


def test_prod_rejects_whitespace_only_jwt_kid() -> None:
    with pytest.raises(ValueError, match="JWT_KID"):
        Config(ENV="prod", **_prod_kwargs(JWT_KID="   "))
