from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.content.domain.entity import SiteContent
from app.core.db.session import session


class ContentRepository:
    async def get(self, key: str) -> SiteContent | None:
        return (
            await session.execute(
                select(SiteContent).where(SiteContent.key == key)
            )
        ).scalar_one_or_none()

    async def upsert(self, key: str, content: dict[str, object]) -> SiteContent:
        stmt = (
            pg_insert(SiteContent)
            .values(key=key, content=content)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"content": content, "updated_at": func.now()},
            )
        )
        await session.execute(stmt)
        await session.flush()
        row = await self.get(key)
        assert row is not None
        return row
