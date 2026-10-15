from functools import lru_cache

from app.core.exception.error_base import TagNotFound
from app.post.infrastructure.repository import PostRepository
from app.tag.application.schemas import TagDetailResponse, TagRead
from app.tag.domain.entity import Tag
from app.tag.infrastructure.repository import TagRepository


class TagService:
    def __init__(self) -> None:
        self.tag_repo = TagRepository()
        self.post_repo = PostRepository()

    async def list_with_counts(self) -> list[TagRead]:
        rows = await self.tag_repo.list_with_counts()
        return [TagRead(name=t.name, count=c) for t, c in rows]

    async def get_detail(self, name: str) -> TagDetailResponse:
        tag: Tag | None = await self.tag_repo.get(name)
        if tag is None:
            raise TagNotFound(name)
        count = await self.tag_repo.get_count(name)
        posts = await self.post_repo.list_by_tag(name)
        return TagDetailResponse.model_validate(
            {
                "tag": TagRead(name=tag.name, count=count),
                "posts": list(posts),
            }
        )


@lru_cache
def _tag_service() -> TagService:
    return TagService()


async def get_tag_service() -> TagService:
    # async def: a plain def dependency runs in the threadpool, where every
    # request would queue behind bcrypt logins.
    return _tag_service()
