import datetime as dt

from pydantic import BaseModel, ConfigDict, field_validator
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

    @field_validator("content")
    @classmethod
    def must_be_dict(cls, v: object) -> dict[str, object]:
        if not isinstance(v, dict):
            raise TypeError("content must be a JSON object")
        return v
