"""Smoke / unit test fixtures.

Integration tests live under `tests/integration/` and are skipped when
`TEST_DATABASE_URL` is not set. Run them explicitly with:

    TEST_DATABASE_URL=postgresql+asyncpg://blog:blog@localhost:5432/blog \
        pytest -m integration
"""

import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.root_router import root_router
from app.core.config.config import loader
from app.core.exception.error_base import CustomException
from app.core.exception.exception_handlers import custom_exception_handler

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

TEST_RSA_KID = "test-kid"


def _generate_test_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


# Generated once per pytest run. Stable for the duration of the process so that
# `keys.private_key()` caches the parsed key consistently across tests.
TEST_RSA_PRIVATE_PEM = _generate_test_pem()


@pytest.fixture(autouse=True)
def _patch_test_rsa_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the test RSA key + kid into the currently-cached Config.

    Tests that swap `loader._config` for a fresh Config (e.g. test_auth_modes)
    must supply JWT_PRIVATE_KEY_PEM / JWT_KID themselves — this patch only
    affects the instance live at the start of the test.
    """
    cfg = loader.config
    monkeypatch.setattr(cfg, "JWT_PRIVATE_KEY_PEM", TEST_RSA_PRIVATE_PEM)
    monkeypatch.setattr(cfg, "JWT_KID", TEST_RSA_KID)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(root_router)
    application.add_exception_handler(CustomException, custom_exception_handler)
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
