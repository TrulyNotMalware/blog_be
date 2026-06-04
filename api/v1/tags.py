from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.tag.application.schemas import TagDetailResponse, TagRead
from app.tag.application.service import TagService, get_tag_service

router = APIRouter(prefix="/tags", tags=["tags"])

_PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"

ServiceDep = Annotated[TagService, Depends(get_tag_service)]


@router.get(
    "",
    response_model=list[TagRead],
    response_model_by_alias=True,
)
async def list_tags(response: Response, service: ServiceDep) -> list[TagRead]:
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return await service.list_with_counts()


@router.get(
    "/{name}",
    response_model=TagDetailResponse,
    response_model_by_alias=True,
)
async def get_tag(
    name: str,
    response: Response,
    service: ServiceDep,
) -> TagDetailResponse:
    response.headers["Cache-Control"] = _PUBLIC_CACHE
    return await service.get_detail(name)
