from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginatedResponse
from app.post.application.schemas import PostPublic
from app.post.application.service import PostService, get_post_service

router = APIRouter(prefix="/search", tags=["search"])

ServiceDep = Annotated[PostService, Depends(get_post_service)]


@router.get(
    "",
    response_model=PaginatedResponse[PostPublic],
    response_model_by_alias=True,
)
async def search_posts(
    service: ServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
) -> PaginatedResponse[PostPublic]:
    items, total = await service.search(q=q, page=page, page_size=page_size)
    return PaginatedResponse[PostPublic].build(
        items=[PostPublic.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )
