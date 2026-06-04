from app.core.utils.slug import normalize_tag, slugify


def test_slugify_basic() -> None:
    assert slugify("Hello World") == "hello-world"


def test_slugify_lowercases() -> None:
    assert slugify("TypeScript Note") == "typescript-note"


def test_normalize_tag_strips_caps() -> None:
    assert normalize_tag("TypeScript") == "typescript"
