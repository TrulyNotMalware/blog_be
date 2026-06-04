from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.pagination import PaginatedResponse
from app.core.security.auth import require_admin
from app.post.application.schemas import PostAdmin, PostKind, PostStatus
from app.post.application.service import PostService, get_post_service

router = APIRouter(prefix="/admin/posts", tags=["admin"])

ServiceDep = Annotated[PostService, Depends(get_post_service)]


@router.get(
    "",
    response_model=PaginatedResponse[PostAdmin],
    response_model_by_alias=True,
)
async def list_admin_posts(
    service: ServiceDep,
    _: Annotated[str, Depends(require_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
    tag: str | None = None,
    kind: PostKind | None = None,
    status: PostStatus | None = None,
) -> PaginatedResponse[PostAdmin]:
    items, total = await service.list_all(
        page=page, page_size=page_size, tag=tag, kind=kind, status=status
    )
    return PaginatedResponse[PostAdmin].build(
        items=[PostAdmin.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{post_id}",
    response_model=PostAdmin,
    response_model_by_alias=True,
)
async def get_admin_post(
    post_id: str,
    service: ServiceDep,
    _: Annotated[str, Depends(require_admin)],
) -> PostAdmin:
    post = await service.get_by_id(post_id)
    return PostAdmin.model_validate(post)
