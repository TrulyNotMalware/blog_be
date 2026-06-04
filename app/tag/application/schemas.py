from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.post.application.schemas import PostPublic


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class TagRead(_Camel):
    name: str
    count: int


class TagDetailResponse(_Camel):
    tag: TagRead
    posts: list[PostPublic]
