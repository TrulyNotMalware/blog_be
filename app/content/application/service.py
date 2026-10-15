import json
from functools import lru_cache

from app.content.application.schemas import ContentRead
from app.content.domain.entity import SiteContent
from app.content.infrastructure.repository import ContentRepository
from app.core.db.transactional import Transactional
from app.core.exception.codes import ErrorCode
from app.core.exception.error_base import ContentNotFound, CustomException

_MAX_CONTENT_BYTES = 64 * 1024  # 64 KB


class ContentService:
    def __init__(self) -> None:
        self.repo = ContentRepository()

    async def get(self, key: str) -> ContentRead:
        row: SiteContent | None = await self.repo.get(key)
        if row is None:
            raise ContentNotFound(key)
        return ContentRead.model_validate(row)

    @Transactional()
    async def upsert(self, key: str, content: dict[str, object]) -> ContentRead:
        serialized = json.dumps(content, ensure_ascii=False)
        if len(serialized.encode()) > _MAX_CONTENT_BYTES:
            raise CustomException(
                ErrorCode.VALIDATION_ERROR,
                "content exceeds 64 KB limit",
                422,
            )
        row = await self.repo.upsert(key, content)
        return ContentRead.model_validate(row)


@lru_cache
def get_content_service() -> ContentService:
    return ContentService()
