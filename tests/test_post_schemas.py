import pytest
from pydantic import ValidationError

from app.post.application.schemas import PostUpdate


@pytest.mark.parametrize(
    "field",
    ["title", "excerpt", "date", "readTime", "kind", "featured", "status"],
)
def test_post_update_rejects_null_for_not_null_column(field: str) -> None:
    with pytest.raises(ValidationError):
        PostUpdate.model_validate({field: None})


def test_post_update_allows_null_content() -> None:
    update = PostUpdate.model_validate({"content": None})
    assert update.model_dump(exclude_unset=True) == {"content": None}


def test_post_update_omitted_fields_stay_unset() -> None:
    update = PostUpdate.model_validate({"title": "New"})
    assert update.model_dump(exclude_unset=True) == {"title": "New"}
