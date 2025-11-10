"""API router aggregator."""

from fastapi import APIRouter

from .auth import router as auth_router
from .documents import router as documents_router
from .upload import router as upload_router
from .user_settings import router as user_settings_router
from .files import router as files_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(upload_router, prefix="/api", tags=["upload"])
api_router.include_router(documents_router, prefix="/api", tags=["documents"])
api_router.include_router(user_settings_router)
api_router.include_router(files_router, prefix="/api", tags=["files"])

__all__ = ["api_router"]


