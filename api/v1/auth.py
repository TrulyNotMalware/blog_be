from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.admin.infrastructure.repository import increment_token_version, upsert_admin
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
    return TokenPair(
        access_token=issue_access_token(cfg.ADMIN_USERNAME, admin.token_version),
        refresh_token=issue_refresh_token(cfg.ADMIN_USERNAME, admin.token_version),
    )


@router.post("/refresh", response_model=TokenPair, response_model_by_alias=True)
async def refresh(payload: RefreshRequest) -> TokenPair:
    """Rotate tokens. The refresh token must still match the current
    `admins.token_version` — logout / password change invalidates both."""
    subject, tv = await verify_refresh_token(payload.refresh_token)
    return TokenPair(
        access_token=issue_access_token(subject, tv),
        refresh_token=issue_refresh_token(subject, tv),
    )


@router.post("/logout", status_code=200)
@Transactional()
async def logout(
    subject: Annotated[str, Depends(require_admin)],
) -> dict[str, str]:
    await increment_token_version(subject)
    return {"status": "ok"}
