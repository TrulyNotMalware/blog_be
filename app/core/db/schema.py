"""Schema bootstrap — thin wrapper that ensures the ORM mappings are imported
before delegating to `init_tables()` on the writer engine."""

import app.admin.domain.entity
import app.content.domain.entity
import app.post.domain.entity
import app.tag.domain.entity  # noqa: F401 — registers Tag on Base.metadata
from app.core.db.session import init_tables


async def init_schema() -> None:
    await init_tables()
