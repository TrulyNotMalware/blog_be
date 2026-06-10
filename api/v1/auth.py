from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.admin.infrastructure.repository import (
    get_admin,
    get_refresh_token,
    increment_token_version,
    mark_refresh_token_rotated,
    record_refresh_token,
    revoke_family_committed,
    revoke_refresh_tokens,
    upsert_admin,
)
from app.core.config.config import loader
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
@Transactional()
async def refresh(payload: RefreshRequest) -> TokenPair:
    """Rotate tokens with reuse detection.

    The refresh token must still match the current `admins.token_version`
    (logout / password change invalidates both). Beyond that, the presented
    jti is looked up:
      - unknown / revoked / expired -> 401.
      - already `rotated` -> REUSE DETECTED: a token already exchanged once is
        being replayed. Bump token_version (kills the whole access+refresh
        family, forcing re-login) and revoke all of this subject's refresh
        tokens. 401.
      - `active` -> rotate: mark old jti `rotated`, persist the new jti, issue
        a fresh pair.
    Rotate + insert + reuse-revoke all run in this one @Transactional() so the
    family state stays atomic.
    """
    subject, tv, jti = verify_refresh_token(payload.refresh_token)

    admin = await get_admin(subject)
    if admin is None or admin.token_version != tv:
        raise Unauthorized("Token has been revoked")

    row = await get_refresh_token(jti)
    if row is None or row.status == "revoked":
        raise Unauthorized("Token has been revoked")
    if row.status == "rotated":
        # Replay of an already-rotated token — treat as theft, kill the family.
        # Commit the kill independently: this request's @Transactional() would
        # otherwise roll it back when we raise 401 below.
        await revoke_family_committed(subject)
        raise Unauthorized("Token reuse detected")
    if row.expires_at <= datetime.now(tz=UTC):
        raise Unauthorized("Token has been revoked")

    await mark_refresh_token_rotated(jti)
    new_refresh, new_jti = issue_refresh_token(subject, tv)
    await record_refresh_token(new_jti, subject, _refresh_expires_at())
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
