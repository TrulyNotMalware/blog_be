import datetime as dt

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.session import Base


class SiteContent(Base):
    __tablename__ = "site_contents"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
