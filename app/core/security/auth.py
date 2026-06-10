from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config.config import JWT_ALGORITHM, loader
from app.core.exception.error_base import Forbidden, Unauthorized
from app.core.security import keys

_bearer_scheme = HTTPBearer(auto_error=False)

TokenType = Literal["access", "refresh"]


def _issue(
    subject: str, token_version: int, *, kind: TokenType, ttl_minutes: int
) -> tuple[str, str]:
    """Encode a token. Returns (encoded_token, jti)."""
    cfg = loader.config
    now = datetime.now(tz=UTC)
    # Random jti ensures each issuance is byte-unique even within the same
    # second (rotation tests, rapid refresh). For refresh tokens this is
    # persisted and validated server-side to enable rotation + reuse detection.
    jti = uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": cfg.JWT_ISSUER,
        "aud": cfg.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "tv": token_version,
        "typ": kind,
        "jti": jti,
    }
    token = jwt.encode(
        payload,
        keys.private_key(),
        algorithm=JWT_ALGORITHM,
        headers={"kid": cfg.JWT_KID},
    )
    return token, jti


def issue_access_token(subject: str, token_version: int) -> str:
    token, _ = _issue(
        subject,
        token_version,
        kind="access",
        ttl_minutes=loader.config.JWT_ACCESS_EXPIRE_MINUTES,
    )
    return token


def issue_refresh_token(subject: str, token_version: int) -> tuple[str, str]:
    """Issue a refresh token. Returns (token, jti) so callers can persist it."""
    return _issue(
        subject,
        token_version,
        kind="refresh",
        ttl_minutes=loader.config.JWT_REFRESH_EXPIRE_MINUTES,
    )


def decode_token(token: str) -> dict[str, Any]:
    cfg = loader.config
    try:
        return jwt.decode(
            token,
            keys.public_key(),
            algorithms=[JWT_ALGORITHM],
            issuer=cfg.JWT_ISSUER,
            audience=cfg.JWT_AUDIENCE,
        )
    except jwt.PyJWTError as e:
        raise Unauthorized("Invalid or expired token") from e


async def _verify_subject(payload: dict[str, Any], expected_type: TokenType) -> str:
    """Shared validation: subject + token type + token_version vs DB."""
    from app.admin.infrastructure.repository import get_admin
    from app.core.db.session import session

    subject = payload.get("sub")
    if not isinstance(subject, str) or subject != loader.config.ADMIN_USERNAME:
        raise Forbidden()
    if payload.get("typ") != expected_type:
        raise Unauthorized("Wrong token type")
    token_version = payload.get("tv")
    if not isinstance(token_version, int):
        raise Unauthorized("Token missing version claim")
    try:
        admin = await get_admin(subject)
        if admin is None or admin.token_version != token_version:
            raise Unauthorized("Token has been revoked")
    finally:
        # The read above autobegins a transaction on the scoped session. Release
        # it so the endpoint's @Transactional() can open a fresh one that will
        # actually commit. Without this the endpoint runs in "join" mode and
        # SQLAlchemyMiddleware rolls back on cleanup.
        if session().in_transaction():
            await session.rollback()
    return subject


async def require_admin(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Admin authentication.

    - local/test: verify the Bearer JWT directly (signature + iss + exp + typ +
      token_version).
    - prod: trust the gateway-validated `X-User-ID` header. Network-level
      isolation (NetworkPolicy) MUST prevent external callers from setting it.
      Note: `token_version` is not re-checked, so revocation lags by the access
      TTL — keep that TTL short.
    """
    if loader.config.is_prod:
        return _require_admin_from_header(request)

    if creds is None:
        raise Unauthorized()
    payload = decode_token(creds.credentials)
    return await _verify_subject(payload, expected_type="access")


def _require_admin_from_header(request: Request) -> str:
    """Trust the gateway-validated `X-User-ID`. Requires network-level isolation
    (e.g. K8s NetworkPolicy) so external callers cannot reach this code path.
    """
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise Unauthorized()
    if user_id != loader.config.ADMIN_USERNAME:
        raise Forbidden()
    return user_id


def verify_refresh_token(token: str) -> tuple[str, int, str]:
    """Validate a refresh token's signature + claims (no DB access).

    Returns (subject, token_version, jti). The caller checks `token_version`
    against the DB and runs jti rotation / reuse detection inside its own
    transaction — keeping that work atomic.
    """
    payload = decode_token(token)
    subject = payload.get("sub")
    if not isinstance(subject, str) or subject != loader.config.ADMIN_USERNAME:
        raise Forbidden()
    if payload.get("typ") != "refresh":
        raise Unauthorized("Wrong token type")
    tv = payload.get("tv")
    if not isinstance(tv, int):
        raise Unauthorized("Token missing version claim")
    jti = payload.get("jti")
    if not isinstance(jti, str):
        raise Unauthorized("Token missing id claim")
    return subject, tv, jti
