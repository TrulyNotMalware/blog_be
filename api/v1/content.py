import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.content.application.schemas import ContentRead, ContentWrite
from app.content.application.service import ContentService, get_content_service
from app.core.exception.codes import ErrorCode
from app.core.exception.error_base import CustomException
from app.core.security.auth import require_admin

router = APIRouter(prefix="/content", tags=["content"])

_PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MAX_CONTENT_BYTES = 64 * 1024

ServiceDep = Annotated[ContentService, Depends(get_content_service)]


def _validate_key(key: str) -> None:
    if not _KEY_RE.match(key):
        raise CustomException(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid content key: '{key}'. Must match ^[a-z0-9][a-z0-9_-]{{0,63}}$",
            422,
        )


@router.get(
    "/{key}",
    response_model=ContentRead,
    response_model_by_alias=True,
)
async def get_content(
    key: str,
    response: Response,
    service: ServiceDep,
) -> ContentRead:
    _validate_key(key)
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return await service.get(key)


@router.put(
    "/{key}",
    response_model=ContentRead,
    response_model_by_alias=True,
)
async def put_content(
    key: str,
    body: ContentWrite,
    service: ServiceDep,
    _admin: Annotated[str, Depends(require_admin)],
) -> ContentRead:
    _validate_key(key)
    serialized = json.dumps(body.content, ensure_ascii=False)
    if len(serialized.encode()) > _MAX_CONTENT_BYTES:
        raise CustomException(
            ErrorCode.VALIDATION_ERROR,
            "content exceeds 64 KB limit",
            422,
        )
    return await service.upsert(key, body.content)
