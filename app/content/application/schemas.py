import datetime as dt

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ContentRead(_Camel):
    key: str
    content: dict[str, object]
    updated_at: dt.datetime


class ContentWrite(BaseModel):
    content: dict[str, object]
