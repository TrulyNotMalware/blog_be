from slugify import slugify as _slugify


def slugify(value: str) -> str:
    return _slugify(value, lowercase=True, separator="-")


def normalize_tag(value: str) -> str:
    return slugify(value)
