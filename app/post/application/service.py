from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache

from app.core.db.transactional import Transactional
from app.core.exception.error_base import PostNotFound, SlugConflict
from app.core.utils.slug import normalize_tag, slugify
from app.post.application.schemas import PostCreate, PostUpdate
from app.post.domain.entity import Post, PostKind, PostStatus
from app.post.infrastructure.repository import PostRepository
from app.tag.infrastructure.repository import TagRepository


class PostService:
    def __init__(self) -> None:
        self.post_repo = PostRepository()
        self.tag_repo = TagRepository()

    async def list_all(
        self,
        *,
        page: int,
        page_size: int,
        tag: str | None,
        kind: PostKind | None,
        status: PostStatus | None,
    ) -> tuple[Sequence[Post], int]:
        return await self.post_repo.list_all(
            page=page, page_size=page_size, tag=tag, kind=kind, status=status
        )

    async def list_published(
        self,
        *,
        page: int,
        page_size: int,
        tag: str | None,
        kind: PostKind | None,
    ) -> tuple[Sequence[Post], int]:
        return await self.post_repo.list_published(
            page=page, page_size=page_size, tag=tag, kind=kind
        )

    async def search(
        self,
        *,
        q: str,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Post], int]:
        return await self.post_repo.search(q=q, page=page, page_size=page_size)

    async def get_published(self, post_id: str) -> Post:
        post = await self.post_repo.get_published(post_id)
        if post is None:
            raise PostNotFound(post_id)
        return post

    async def get_nav(self, post_id: str) -> tuple[Post | None, Post | None]:
        post = await self.post_repo.get_published(post_id)
        if post is None:
            raise PostNotFound(post_id)
        return await self.post_repo.get_nav(post)

    async def get_by_id(self, post_id: str) -> Post:
        post = await self.post_repo.get_by_id(post_id)
        if post is None:
            raise PostNotFound(post_id)
        return post

    @Transactional()
    async def create(self, payload: PostCreate) -> Post:
        slug = payload.id or slugify(payload.title)
        if await self.post_repo.exists(slug):
            raise SlugConflict(slug)

        tag_names = [normalize_tag(t) for t in payload.tags]
        tags = await self.tag_repo.ensure(tag_names)

        post = Post(
            id=slug,
            title=payload.title,
            excerpt=payload.excerpt,
            content=payload.content,
            date=payload.date,
            read_time=payload.read_time,
            kind=payload.kind,
            featured=payload.featured,
            status=payload.status,
        )
        post.tags = list(tags)
        await self.post_repo.add(post)
        return post

    @Transactional()
    async def update(self, post_id: str, payload: PostUpdate) -> Post:
        post = await self.get_by_id(post_id)
        data = payload.model_dump(exclude_unset=True)
        new_id = data.pop("id", None)
        tags_update = data.pop("tags", None)
        for key, value in data.items():
            setattr(post, key, value)
        if tags_update is not None:
            names = [normalize_tag(t) for t in tags_update]
            post.tags = list(await self.tag_repo.ensure(names))
        if new_id is not None and new_id != post_id:
            if await self.post_repo.exists(new_id):
                raise SlugConflict(new_id)
            post.id = new_id
        return post

    @Transactional()
    async def delete(self, post_id: str) -> None:
        post = await self.get_by_id(post_id)
        await self.post_repo.delete(post)

    @Transactional()
    async def publish(self, post_id: str) -> Post:
        post = await self.get_by_id(post_id)
        post.status = "published"
        post.date = datetime.now(tz=UTC).date()
        return post


@lru_cache
def get_post_service() -> PostService:
    return PostService()
