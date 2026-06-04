from collections.abc import Sequence

from sqlalchemy import case, desc, func, or_, select

from app.core.db.session import session
from app.post.domain.entity import Post, PostKind, PostStatus, post_tags


class PostRepository:
    async def list_all(
        self,
        *,
        page: int,
        page_size: int,
        tag: str | None,
        kind: PostKind | None,
        status: PostStatus | None,
    ) -> tuple[Sequence[Post], int]:
        base = select(Post)
        if tag is not None:
            base = base.join(post_tags, post_tags.c.post_id == Post.id).where(
                post_tags.c.tag_name == tag
            )
        if kind is not None:
            base = base.where(Post.kind == kind)
        if status is not None:
            base = base.where(Post.status == status)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_stmt)).scalar_one()

        items_stmt = (
            base.order_by(desc(Post.updated_at), Post.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await session.execute(items_stmt)).scalars().unique().all()
        return items, int(total)

    async def list_published(
        self,
        *,
        page: int,
        page_size: int,
        tag: str | None,
        kind: PostKind | None,
    ) -> tuple[Sequence[Post], int]:
        base = select(Post).where(Post.status == "published")
        if tag is not None:
            base = base.join(post_tags, post_tags.c.post_id == Post.id).where(
                post_tags.c.tag_name == tag
            )
        if kind is not None:
            base = base.where(Post.kind == kind)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_stmt)).scalar_one()

        items_stmt = (
            base.order_by(desc(Post.featured), desc(Post.date), Post.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await session.execute(items_stmt)).scalars().unique().all()
        return items, int(total)

    async def get_published(self, post_id: str) -> Post | None:
        stmt = select(Post).where(Post.id == post_id, Post.status == "published")
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, post_id: str) -> Post | None:
        stmt = select(Post).where(Post.id == post_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def exists(self, post_id: str) -> bool:
        stmt = select(func.count()).select_from(Post).where(Post.id == post_id)
        return bool((await session.execute(stmt)).scalar_one())

    async def add(self, post: Post) -> None:
        session.add(post)
        await session.flush()

    async def delete(self, post: Post) -> None:
        await session.delete(post)
        await session.flush()

    async def list_by_tag(self, tag_name: str) -> Sequence[Post]:
        stmt = (
            select(Post)
            .join(post_tags, post_tags.c.post_id == Post.id)
            .where(
                post_tags.c.tag_name == tag_name,
                Post.status == "published",
            )
            .order_by(desc(Post.date), Post.id)
        )
        return (await session.execute(stmt)).scalars().unique().all()

    async def get_nav(self, post: Post) -> tuple[Post | None, Post | None]:
        """Return (prev, next) published posts relative to *post*.

        Ordering: DESC(date), ASC(id). Deliberately ignores `featured` —
        readers expect chronological neighbours regardless of pin status,
        even though list_published sorts pinned posts to the top.
        prev = older (comes after in the list); next = newer (comes before in list).
        """
        # prev: same date but lexicographically greater id, OR earlier date
        prev_stmt = (
            select(Post)
            .where(
                Post.status == "published",
                Post.id != post.id,
                (
                    (Post.date < post.date)
                    | (
                        (Post.date == post.date) & (Post.id > post.id)
                    )
                ),
            )
            .order_by(desc(Post.date), Post.id)
            .limit(1)
        )
        # next: same date but lexicographically smaller id, OR later date
        next_stmt = (
            select(Post)
            .where(
                Post.status == "published",
                Post.id != post.id,
                (
                    (Post.date > post.date)
                    | (
                        (Post.date == post.date) & (Post.id < post.id)
                    )
                ),
            )
            .order_by(Post.date, desc(Post.id))
            .limit(1)
        )
        prev = (await session.execute(prev_stmt)).scalar_one_or_none()
        nxt = (await session.execute(next_stmt)).scalar_one_or_none()
        return prev, nxt

    async def search(
        self,
        *,
        q: str,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Post], int]:
        # Escape ILIKE wildcards (%, _, \) so `q="%"` can't trigger a full-table scan.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        score_expr = (
            case((Post.title.ilike(pattern, escape="\\"), 3), else_=0)
            + case((Post.excerpt.ilike(pattern, escape="\\"), 2), else_=0)
            + case((Post.content.ilike(pattern, escape="\\"), 1), else_=0)
        )
        where_clause = (
            Post.status == "published",
            or_(
                Post.title.ilike(pattern, escape="\\"),
                Post.excerpt.ilike(pattern, escape="\\"),
                Post.content.ilike(pattern, escape="\\"),
            ),
        )
        base = select(Post).where(*where_clause)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_stmt)).scalar_one()

        items_stmt = (
            base.add_columns(score_expr.label("score"))
            .order_by(desc("score"), desc(Post.date))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(items_stmt)).unique().all()
        items = [row[0] for row in rows]
        return items, int(total)
