import inspect
from collections.abc import Callable

import pytest
from httpx import ASGITransport, AsyncClient

from app.content.application.service import get_content_service
from app.core.config.config import loader
from app.post.application.service import get_post_service
from app.server import init_app
from app.tag.application.service import get_tag_service


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
async def test_cors_preflight_allows_every_method_the_api_uses(method: str) -> None:
    # PUT /v1/content/{key} is the only PUT route; its preflight used to get a 400.
    origin = loader.config.cors_origins_list[0]
    transport = ASGITransport(app=init_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.options(
            "/v1/content/about",
            headers={"Origin": origin, "Access-Control-Request-Method": method},
        )
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "factory", [get_post_service, get_tag_service, get_content_service]
)
def test_service_dependencies_stay_on_the_event_loop(
    factory: Callable[..., object],
) -> None:
    # FastAPI runs a plain def dependency in the threadpool, behind bcrypt logins.
    assert inspect.iscoroutinefunction(factory)
