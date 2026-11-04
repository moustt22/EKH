from fastapi import APIRouter

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.departments import router as departments_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(departments_router)
api_router.include_router(users_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(conversations_router)
api_router.include_router(audit_router)
