"""Unit coverage for `app.core.security.keys` — the RSA key loader sitting
between Config (env/Secret) and both the issuer (auth.py) and the JWKS endpoint.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config.config import loader
from app.core.security import keys


def test_private_key_returns_rsa_private_key() -> None:
    pk = keys.private_key()
    assert isinstance(pk, RSAPrivateKey)


def test_public_key_is_derived_from_private() -> None:
    pub = keys.public_key()
    assert isinstance(pub, RSAPublicKey)
    # The public key projection must match the one cryptography hands out from the
    # private key object — guards against keys.public_key() returning a stale or
    # mismatched key, which would silently break signature verification.
    assert pub.public_numbers() == keys.private_key().public_key().public_numbers()


def test_private_key_caches_per_pem() -> None:
    first = keys.private_key()
    second = keys.private_key()
    # Same PEM string — the cache must return the exact same object, not just
    # an equal one, so that downstream signing has no per-call parse cost.
    assert first is second


def test_public_jwk_shape() -> None:
    jwk = keys.public_jwk()
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"
    assert jwk["use"] == "sig"
    assert jwk["kid"] == loader.config.JWT_KID
    assert jwk["n"]
    assert jwk["e"]


def test_private_key_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader.config, "JWT_PRIVATE_KEY_PEM", "")
    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY_PEM"):
        keys.private_key()


def test_private_key_garbage_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader.config, "JWT_PRIVATE_KEY_PEM", "not-a-pem")
    with pytest.raises(ValueError, match=r"(?i)pem|deserialize"):
        keys.private_key()
