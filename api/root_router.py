from fastapi import APIRouter

from api.jwks import router as jwks_router
from api.v1 import v1_router

root_router = APIRouter()
root_router.include_router(v1_router, prefix="/v1")
root_router.include_router(jwks_router)


@root_router.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
