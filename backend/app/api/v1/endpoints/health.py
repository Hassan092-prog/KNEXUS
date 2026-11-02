from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Return a non-sensitive dependency diagnostic; this is not readiness."""
    health_status = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "unknown",
        "pgvector_extension": "unknown",
        "ollama": "unknown",
    }

    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            health_status["database"] = "connected"
        vector_result = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        health_status["pgvector_extension"] = (
            "installed" if vector_result.scalar() == "vector" else "not_installed"
        )
    except Exception:
        health_status["database"] = "unavailable"
        health_status["pgvector_extension"] = "unknown"
        health_status["status"] = "degraded"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            health_status["ollama"] = (
                "online" if response.status_code == 200 else "unhealthy"
            )
    except Exception:
        health_status["ollama"] = "offline"

    return health_status
