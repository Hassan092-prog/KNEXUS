from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Return passive dependency diagnostics without outbound network probes."""
    active_gen_provider = settings.GENERATION_PROVIDER or settings.OLLAMA_PROVIDER
    active_embed_provider = settings.EMBEDDING_PROVIDER

    health_status = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "unknown",
        "pgvector_extension": "unknown",
        "generation": "configured" if active_gen_provider else "not_configured",
        "embedding": "configured" if active_embed_provider else "not_configured",
        "ollama": "configured" if active_gen_provider == "ollama" else "disabled",
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

    return health_status
