from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.admin.infrastructure.repository import (
    claim_refresh_token_rotation,
    get_admin,
    get_refresh_token,
    increment_token_version,
    record_refresh_token,
    revoke_refresh_tokens,
    upsert_admin,
)
from app.core.config.config import loader
from app.core.db.session import session
from app.core.db.transactional import Transactional
from app.core.exception.error_base import Unauthorized
from app.core.security.auth import (
    issue_access_token,
    issue_refresh_token,
    require_admin,
    verify_refresh_token,
)
from app.core.security.password import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Constant-time fallback hash — prevents timing oracle when username doesn't match.
# Generated once at startup so invalid-username paths still do real bcrypt work.
_DUMMY_HASH: str = hash_password("__dummy__sentinel__")


def _refresh_expires_at() -> datetime:
    return datetime.now(tz=UTC) + timedelta(
        minutes=loader.config.JWT_REFRESH_EXPIRE_MINUTES
    )


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LoginRequest(_Camel):
    username: str
    password: str


class TokenPair(_Camel):
    access_token: str
    refresh_token: str


class RefreshRequest(_Camel):
    refresh_token: str


@router.post("/login", response_model=TokenPair, response_model_by_alias=True)
@Transactional()
async def login(payload: LoginRequest) -> TokenPair:
    cfg = loader.config
    # Always run bcrypt regardless of username match to prevent timing oracle.
    username_ok = payload.username == cfg.ADMIN_USERNAME
    expected_hash = cfg.ADMIN_PASSWORD_HASH if username_ok else _DUMMY_HASH
    if not verify_password(payload.password, expected_hash) or not username_ok:
        raise Unauthorized("Invalid credentials")
    admin = await upsert_admin(
        username=cfg.ADMIN_USERNAME,
        password_hash=cfg.ADMIN_PASSWORD_HASH,
    )
    refresh_token, jti = issue_refresh_token(cfg.ADMIN_USERNAME, admin.token_version)
    await record_refresh_token(jti, cfg.ADMIN_USERNAME, _refresh_expires_at())
    return TokenPair(
        access_token=issue_access_token(cfg.ADMIN_USERNAME, admin.token_version),
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenPair, response_model_by_alias=True)
async def refresh(payload: RefreshRequest) -> TokenPair:
    """Rotate tokens with reuse detection.

    The refresh token must still match the current `admins.token_version`
    (logout / password change invalidates both). Then the presented jti is
    rotated via an atomic compare-and-set:
      - `active` (unexpired) -> won the rotation: persist the new jti, issue a
        fresh pair.
      - already `rotated` -> REUSE DETECTED: a token already exchanged once is
        being replayed. Bump token_version (kills the whole access+refresh
        family) and revoke this subject's refresh tokens, then 401.
      - unknown / revoked / expired -> 401.

    The whole thing runs in one explicit transaction (not @Transactional) so the
    reuse-revocation can be COMMITTED before we raise 401 — @Transactional would
    roll it back. The single-connection commit also avoids the pool-starvation
    risk of opening a second session just to persist the kill.
    """
    subject, tv, jti = verify_refresh_token(payload.refresh_token)

    reuse_detected = False
    new_refresh: str | None = None
    async with session.begin():
        admin = await get_admin(subject)
        if admin is None or admin.token_version != tv:
            raise Unauthorized("Token has been revoked")  # read-only → rollback ok

        if await claim_refresh_token_rotation(jti):
            new_refresh, new_jti = issue_refresh_token(subject, tv)
            await record_refresh_token(new_jti, subject, _refresh_expires_at())
        else:
            # Didn't win the claim: an already-`rotated` jti is a replay (theft) →
            # kill the family and COMMIT (don't raise inside the block), then 401
            # outside. Anything else (unknown / revoked / expired-active) is a
            # plain 401 with no writes.
            row = await get_refresh_token(jti)
            if row is not None and row.status == "rotated":
                await increment_token_version(subject)
                await revoke_refresh_tokens(subject)
                reuse_detected = True
            else:
                raise Unauthorized("Token has been revoked")

    if reuse_detected:
        raise Unauthorized("Token reuse detected")

    assert new_refresh is not None  # claim succeeded → set; reuse path returned above
    return TokenPair(
        access_token=issue_access_token(subject, tv),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=200)
@Transactional()
async def logout(
    subject: Annotated[str, Depends(require_admin)],
) -> dict[str, str]:
    await increment_token_version(subject)
    await revoke_refresh_tokens(subject)
    return {"status": "ok"}
