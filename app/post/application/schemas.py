import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

PostKind = Literal["essay", "note", "guide", "compare"]
PostStatus = Literal["published", "draft", "scheduled"]


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


def _flatten_tags(v: object) -> object:
    if isinstance(v, list) and v and not isinstance(v[0], str):
        return [getattr(t, "name", t) for t in v]
    return v


class PostPublic(_Camel):
    """Response shape for public list endpoints (no content/status/views)."""

    id: str
    title: str
    excerpt: str
    tags: list[str]
    date: dt.date
    read_time: str
    kind: PostKind
    featured: bool = False

    @field_validator("tags", mode="before")
    @classmethod
    def _ts(cls, v: object) -> object:
        return _flatten_tags(v)


class PostDetail(PostPublic):
    """Response shape for public detail endpoint (includes content)."""

    content: str | None = None


class PostAdmin(PostDetail):
    """Admin response shape (includes status / views / timestamps)."""

    status: PostStatus
    views: int
    created_at: dt.datetime
    updated_at: dt.datetime


class PostCreate(_Camel):
    id: str | None = None
    title: str
    excerpt: str
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    date: dt.date
    read_time: str
    kind: PostKind
    featured: bool = False
    status: PostStatus = "draft"


class PostUpdate(_Camel):
    id: str | None = None
    title: str | None = None
    excerpt: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    date: dt.date | None = None
    read_time: str | None = None
    kind: PostKind | None = None
    featured: bool | None = None
    status: PostStatus | None = None


class PostNavItem(_Camel):
    """Minimal post shape used in prev/next nav."""

    id: str
    title: str
    excerpt: str
    date: dt.date
    tags: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def _ts(cls, v: object) -> object:
        return _flatten_tags(v)


class PostNavResponse(_Camel):
    prev: PostNavItem | None = None
    next: PostNavItem | None = None
