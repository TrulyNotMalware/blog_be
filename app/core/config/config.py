from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROD_ENV_NAMES = frozenset({"prod", "production"})

# Pinned signing algorithm — see auth.py / keys.py. We deliberately do not
# expose this as a configurable knob: the JWKS endpoint hardcodes "alg":"RS256",
# the gateway pins SignatureAlgorithm.RS256, and a runtime mismatch produces
# silent verification failures that are hard to diagnose.
JWT_ALGORITHM = "RS256"
# Minimum reasonable length for a hop-proof shared secret. Anything shorter
# than this is a placeholder and would be brute-forceable from a constant-time
# comparison side channel.
_MIN_GATEWAY_SHARED_SECRET_LEN = 32


class Config(BaseSettings):
    ENV: str = "local"
    DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"  # noqa: S104
    APP_PORT: int = 8080
    WORKERS: int = 1

    DATABASE_URL: str = "postgresql+asyncpg://blog:blog@localhost:5432/blog"

    CORS_ORIGINS: str = "http://localhost:3000"

    # RS256 (asymmetric). blog_be holds the private PEM and signs; verifiers
    # (gateway, future services) fetch the public key from /.well-known/jwks.json.
    # The algorithm itself is pinned via the module-level `JWT_ALGORITHM` constant.
    JWT_PRIVATE_KEY_PEM: str = ""
    JWT_KID: str = "v1"
    # Short-lived access token + long-lived refresh token (rotation on refresh).
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    JWT_ISSUER: str = "blog-be"
    # `aud` claim — identifies which verifier(s) the token is intended for. Defaults to
    # this service's own identifier so a leaked token cannot be replayed against another
    # backend that happens to trust this issuer's signing key.
    JWT_AUDIENCE: str = "blog-be"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""

    # Shared secret carried in `X-Gateway-Auth` to prove a request traversed the
    # gateway. Empty = enforcement disabled (must be set in prod).
    GATEWAY_SHARED_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _prod_checks(self) -> Config:
        if self.is_prod:
            self._check_prod_jwt_private_key()
            # Whitespace-only kid is still effectively unset: the gateway's
            # KidPresenceValidator rejects blank kids, so issuance would
            # silently mint tokens no verifier accepts.
            if not self.JWT_KID.strip():
                msg = "JWT_KID must be a non-blank string in prod"
                raise ValueError(msg)
            self._check_prod_gateway_secret()
            if self.DEBUG:
                object.__setattr__(self, "DEBUG", False)
        return self

    def _check_prod_jwt_private_key(self) -> None:
        pem = self.JWT_PRIVATE_KEY_PEM.strip()
        if not pem:
            msg = "JWT_PRIVATE_KEY_PEM must be configured in prod"
            raise ValueError(msg)
        try:
            key = serialization.load_pem_private_key(
                pem.encode("utf-8"), password=None
            )
        except Exception as e:
            # Boot must fail loudly here rather than at first /auth/login when
            # `keys.private_key()` is called — operators see the misconfiguration
            # in the crash log instead of as a 500 in production traffic.
            msg = "JWT_PRIVATE_KEY_PEM is not a valid PEM-encoded private key"
            raise ValueError(msg) from e
        if not isinstance(key, RSAPrivateKey):
            msg = "JWT_PRIVATE_KEY_PEM must be an RSA key (RS256 is pinned)"
            raise TypeError(msg)

    def _check_prod_gateway_secret(self) -> None:
        # Prod auth (`require_admin`) trusts X-User-ID stamped by the gateway.
        # An empty GATEWAY_SHARED_SECRET silently disables the hop-proof check
        # in GatewaySharedSecretMiddleware, so any pod that can reach blog_be
        # directly (NetworkPolicy bypass, future ingress mistake) would inherit
        # admin trust by forging the header. Enforce it here at startup.
        secret = self.GATEWAY_SHARED_SECRET.strip()
        if not secret:
            msg = (
                "GATEWAY_SHARED_SECRET must be set in prod — "
                "blank disables hop-proof and lets header-spoofers gain admin"
            )
            raise ValueError(msg)
        if len(secret) < _MIN_GATEWAY_SHARED_SECRET_LEN:
            msg = (
                "GATEWAY_SHARED_SECRET must be at least "
                f"{_MIN_GATEWAY_SHARED_SECRET_LEN} chars in prod "
                f"(got {len(secret)})"
            )
            raise ValueError(msg)

    @property
    def is_prod(self) -> bool:
        """Normalize ENV variants (prod/production, casing) into one boolean.

        Always go through this property — direct `ENV == "prod"` comparisons
        miss the `production` spelling and fall out of sync.
        """
        return self.ENV.lower() in PROD_ENV_NAMES

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


def _resolve_env_files() -> tuple[Path, ...]:
    """Layered env files, Next.js-style.

    Load order (later files override earlier ones):
        .env  <  .env.{env}  <  .env.local  <  .env.{env}.local

    `{env}` comes from the `ENV` environment variable, set by `main.py --env`.
    Missing files are silently skipped.
    """
    env = os.environ.get("ENV", "local").lower()
    candidates = [
        Path(".env"),
        Path(f".env.{env}"),
        Path(".env.local"),
        Path(f".env.{env}.local"),
    ]
    # Read both spellings so `.env.prod` and `.env.production` are interchangeable.
    if env in PROD_ENV_NAMES:
        for alias in PROD_ENV_NAMES - {env}:
            candidates.extend(
                [
                    Path(f".env.{alias}"),
                    Path(f".env.{alias}.local"),
                ],
            )
    return tuple(p for p in candidates if p.is_file())


class ConfigLoader:
    def __init__(self) -> None:
        self._config: Config | None = None

    @property
    def config(self) -> Config:
        if self._config is None:
            files = _resolve_env_files()
            # `_env_file` is the pydantic-settings runtime override for the
            # class-level `env_file` setting. Passing a tuple loads each in
            # order and merges; later files override earlier ones.
            self._config = Config(_env_file=files or None)  # type: ignore[call-arg]
        return self._config


loader = ConfigLoader()
