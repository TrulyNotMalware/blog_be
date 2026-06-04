from collections.abc import Sequence

from sqlalchemy import asc, desc, func, select

from app.core.db.session import session
from app.post.domain.entity import Post, post_tags
from app.tag.domain.entity import Tag


class TagRepository:
    async def list_with_counts(self) -> Sequence[tuple[Tag, int]]:
        count_expr = func.count(Post.id).label("post_count")
        stmt = (
            select(Tag, count_expr)
            .outerjoin(post_tags, post_tags.c.tag_name == Tag.name)
            .outerjoin(
                Post,
                (Post.id == post_tags.c.post_id) & (Post.status == "published"),
            )
            .group_by(Tag.name)
            .order_by(desc(count_expr), asc(Tag.name))
        )
        rows = (await session.execute(stmt)).all()
        return [(t, int(c)) for t, c in rows]

    async def get(self, name: str) -> Tag | None:
        return (
            await session.execute(select(Tag).where(Tag.name == name))
        ).scalar_one_or_none()

    async def get_count(self, name: str) -> int:
        stmt = (
            select(func.count(Post.id))
            .select_from(Post)
            .join(post_tags, post_tags.c.post_id == Post.id)
            .where(
                post_tags.c.tag_name == name,
                Post.status == "published",
            )
        )
        return int((await session.execute(stmt)).scalar_one())

    async def get_many(self, names: Sequence[str]) -> Sequence[Tag]:
        if not names:
            return []
        return (
            (await session.execute(select(Tag).where(Tag.name.in_(names))))
            .scalars()
            .all()
        )

    async def ensure(self, names: Sequence[str]) -> Sequence[Tag]:
        """Return Tag rows for every name, creating any that are missing."""
        if not names:
            return []
        existing = list(await self.get_many(names))
        existing_names = {t.name for t in existing}
        new_tags = [Tag(name=n) for n in names if n not in existing_names]
        for t in new_tags:
            session.add(t)
        if new_tags:
            await session.flush()
        return existing + new_tags
