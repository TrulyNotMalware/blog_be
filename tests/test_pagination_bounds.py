import pytest
from httpx import AsyncClient

from app.core.pagination import MAX_PAGE


@pytest.mark.parametrize("path", ["/v1/posts", "/v1/search?q=a"])
@pytest.mark.parametrize("page", [MAX_PAGE + 1, 10**20])
async def test_page_above_max_is_rejected(
    client: AsyncClient, path: str, page: int
) -> None:
    # 10**20 overflows the int64 OFFSET; it must be a 422, not a database error.
    sep = "&" if "?" in path else "?"
    r = await client.get(f"{path}{sep}page={page}")
    assert r.status_code == 422
