"""JWKS endpoint shape check + end-to-end "issue here, verify from JWKS"
proof that verifiers (gateway, future services) can actually consume what
this server publishes.
"""

from __future__ import annotations

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.root_router import root_router
from app.core.security.auth import issue_access_token
from tests.conftest import TEST_RSA_KID


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(root_router)
    return app


@pytest.mark.asyncio
async def test_jwks_endpoint_returns_signing_public_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        r = await c.get("/.well-known/jwks.json")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("keys"), list)
    assert len(body["keys"]) == 1
    jwk = body["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"
    assert jwk["use"] == "sig"
    assert jwk["kid"] == TEST_RSA_KID
    # RSA JWK must expose modulus + exponent.
    assert jwk["n"]
    assert jwk["e"]


@pytest.mark.asyncio
async def test_jwks_published_key_can_verify_issued_token() -> None:
    """Mint a token via the normal issuance path, then verify it using ONLY
    the JWK published over the wire (n/e/kid). This guards against shape
    regressions where the JWKS would look correct but not actually be usable
    by a stranger verifier (kid mismatch, alg confusion, etc.)."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        r = await c.get("/.well-known/jwks.json")
    assert r.status_code == 200
    jwk = r.json()["keys"][0]

    token = issue_access_token(subject="admin", token_version=1)

    # The verifier here pretends to be an external service: no access to
    # `keys.public_key()`, only the JWKS payload.
    pubkey = jwt.PyJWK.from_dict(jwk).key
    decoded = jwt.decode(
        token,
        pubkey,
        algorithms=["RS256"],
        issuer="blog-be",
        audience="blog-be",
    )
    assert decoded["sub"] == "admin"
    assert decoded["typ"] == "access"
    assert decoded["aud"] == "blog-be"

    # And the kid in the token header must point at the JWK kid.
    header = jwt.get_unverified_header(token)
    assert header["kid"] == jwk["kid"]


@pytest.mark.asyncio
async def test_external_verifier_rejects_wrong_audience() -> None:
    """An external verifier that expects a different `aud` must reject the token.
    Catches cross-service token replay: a blog-be token must NOT verify against
    a verifier configured for `file-be`, even though signature + issuer match.
    """
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://t"
    ) as c:
        r = await c.get("/.well-known/jwks.json")
    jwk = r.json()["keys"][0]
    pubkey = jwt.PyJWK.from_dict(jwk).key

    token = issue_access_token(subject="admin", token_version=1)

    with pytest.raises(jwt.InvalidAudienceError):
        jwt.decode(
            token,
            pubkey,
            algorithms=["RS256"],
            issuer="blog-be",
            audience="file-be",
        )
