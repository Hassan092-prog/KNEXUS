from fastapi import APIRouter
from app.api.v1.endpoints import documents, health, query

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(query.router, tags=["Query"])
