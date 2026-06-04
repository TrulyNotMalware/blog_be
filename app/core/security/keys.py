"""RSA key loading for RS256 JWT issuance and JWKS serving.

The PEM is parsed once per process and cached. Rotation works by updating
`JWT_PRIVATE_KEY_PEM` (a new Secret value) and restarting the pod — the cache
is keyed on the PEM string itself, so a different PEM yields a fresh load.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config.config import loader

_PRIVATE_CACHE: dict[str, RSAPrivateKey] = {}


def private_key() -> RSAPrivateKey:
    pem = loader.config.JWT_PRIVATE_KEY_PEM
    if not pem:
        msg = "JWT_PRIVATE_KEY_PEM is not configured"
        raise RuntimeError(msg)
    cached = _PRIVATE_CACHE.get(pem)
    if cached is not None:
        return cached
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, RSAPrivateKey):
        msg = "JWT_PRIVATE_KEY_PEM must be an RSA private key"
        raise TypeError(msg)
    _PRIVATE_CACHE[pem] = key
    return key


def public_key() -> RSAPublicKey:
    return private_key().public_key()


def public_jwk() -> dict[str, Any]:
    """Public key as a JWK with `kid`, `use=sig`, `alg=RS256` populated."""
    # Local import keeps the JWKS-only dependency out of the auth hot path.
    from jwt.algorithms import RSAAlgorithm

    jwk_raw = RSAAlgorithm.to_jwk(public_key())
    jwk: dict[str, Any] = (
        json.loads(jwk_raw) if isinstance(jwk_raw, str) else dict(jwk_raw)
    )
    from app.core.config.config import JWT_ALGORITHM

    jwk["kid"] = loader.config.JWT_KID
    jwk["use"] = "sig"
    jwk["alg"] = JWT_ALGORITHM
    return jwk
