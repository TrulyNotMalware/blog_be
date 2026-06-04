import datetime as dt
from typing import TYPE_CHECKING, ClassVar, Literal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.session import Base

if TYPE_CHECKING:
    from app.tag.domain.entity import Tag

PostKind = Literal["essay", "note", "guide", "compare"]
PostStatus = Literal["published", "draft", "scheduled"]

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column(
        "post_id",
        String,
        ForeignKey("posts.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_name",
        String,
        ForeignKey("tags.name", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_post_tags_tag_name", "tag_name"),
)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    excerpt: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    read_time: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[PostKind] = mapped_column(String, nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        String, nullable=False, default="published"
    )
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary=post_tags,
        lazy="selectin",
        order_by="Tag.name",
    )

    __table_args__ = (
        Index("ix_posts_status_featured_date", "status", "featured", "date"),
        Index("ix_posts_kind", "kind"),
        Index("ix_posts_date", "date"),
    )

    __mapper_args__: ClassVar[dict[str, object]] = {"eager_defaults": True}
