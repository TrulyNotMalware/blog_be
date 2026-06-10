from fastapi import APIRouter

from api.v1.admin import router as admin_router
from api.v1.auth import router as auth_router
from api.v1.content import router as content_router
from api.v1.posts import router as posts_router
from api.v1.search import router as search_router
from api.v1.tags import router as tags_router

v1_router = APIRouter()
v1_router.include_router(posts_router)
v1_router.include_router(tags_router)
v1_router.include_router(auth_router)
v1_router.include_router(admin_router)
v1_router.include_router(search_router)
v1_router.include_router(content_router)
