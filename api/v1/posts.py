from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.pagination import PaginatedResponse
from app.core.security.auth import require_admin
from app.post.application.schemas import (
    PostAdmin,
    PostCreate,
    PostDetail,
    PostKind,
    PostNavItem,
    PostNavResponse,
    PostPublic,
    PostUpdate,
)
from app.post.application.service import PostService, get_post_service

router = APIRouter(prefix="/posts", tags=["posts"])

_PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"

ServiceDep = Annotated[PostService, Depends(get_post_service)]


@router.get(
    "",
    response_model=PaginatedResponse[PostPublic],
    response_model_by_alias=True,
)
async def list_posts(
        response: Response,
        service: ServiceDep,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
        tag: str | None = None,
        kind: PostKind | None = None,
) -> PaginatedResponse[PostPublic]:
    items, total = await service.list_published(
        page=page, page_size=page_size, tag=tag, kind=kind
    )
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return PaginatedResponse[PostPublic].build(
        items=[PostPublic.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{post_id}",
    response_model=PostDetail,
    response_model_by_alias=True,
)
async def get_post(
        post_id: str,
        response: Response,
        service: ServiceDep,
) -> PostDetail:
    post = await service.get_published(post_id)
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return PostDetail.model_validate(post)


@router.get(
    "/{post_id}/nav",
    response_model=PostNavResponse,
    response_model_by_alias=True,
)
async def get_post_nav(
        post_id: str,
        response: Response,
        service: ServiceDep,
) -> PostNavResponse:
    prev, nxt = await service.get_nav(post_id)
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return PostNavResponse(
        prev=PostNavItem.model_validate(prev) if prev else None,
        next=PostNavItem.model_validate(nxt) if nxt else None,
    )


@router.post(
    "",
    response_model=PostAdmin,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
        payload: PostCreate,
        service: ServiceDep,
        _: Annotated[str, Depends(require_admin)],
) -> PostAdmin:
    post = await service.create(payload)
    return PostAdmin.model_validate(post)


@router.patch(
    "/{post_id}",
    response_model=PostAdmin,
    response_model_by_alias=True,
)
async def patch_post(
        post_id: str,
        payload: PostUpdate,
        service: ServiceDep,
        _: Annotated[str, Depends(require_admin)],
) -> PostAdmin:
    post = await service.update(post_id, payload)
    return PostAdmin.model_validate(post)


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_post(
        post_id: str,
        service: ServiceDep,
        _: Annotated[str, Depends(require_admin)],
) -> Response:
    await service.delete(post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{post_id}/publish",
    response_model=PostAdmin,
    response_model_by_alias=True,
)
async def publish_post(
        post_id: str,
        service: ServiceDep,
        _: Annotated[str, Depends(require_admin)],
) -> PostAdmin:
    post = await service.publish(post_id)
    return PostAdmin.model_validate(post)
