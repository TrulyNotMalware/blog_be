from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

# Without an upper bound a huge page number overflows the int64 OFFSET and the
# request fails in asyncpg with a 500 instead of a 422.
MAX_PAGE = 10_000

PageQuery = Annotated[int, Query(ge=1, le=MAX_PAGE)]
PageSizeQuery = Annotated[int, Query(ge=1, le=100, alias="pageSize")]


class PaginatedResponse[T](BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=page * page_size < total,
        )
