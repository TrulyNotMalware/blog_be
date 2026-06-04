"""RFC 7517 JWKS endpoint.

Internal-only: NetworkPolicy restricts callers to the api-service namespace
(gateway pods). Single kid today — rotate by replacing the Secret and restarting.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.security import keys

router = APIRouter()


@router.get("/.well-known/jwks.json", tags=["jwks"])
async def jwks() -> dict[str, list[dict[str, Any]]]:
    return {"keys": [keys.public_jwk()]}
