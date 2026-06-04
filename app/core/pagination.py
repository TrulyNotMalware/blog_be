from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


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
