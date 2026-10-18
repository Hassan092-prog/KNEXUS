from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    System health check endpoint.
    Verifies API status, PostgreSQL connection (with pgvector), and Ollama reachability.
    """
    health_status = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "unknown",
        "pgvector_extension": "unknown",
        "ollama": "unknown",
    }

    # Check Database connection & pgvector extension
    try:
        result = await db.execute(text("SELECT 1;"))
        if result.scalar() == 1:
            health_status["database"] = "connected"

        # Check if vector extension is active
        vector_res = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        )
        if vector_res.scalar() == "vector":
            health_status["pgvector_extension"] = "installed"
        else:
            health_status["pgvector_extension"] = "not_installed (run 'CREATE EXTENSION vector;')"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check Ollama reachability (non-blocking / soft check)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                health_status["ollama"] = f"online (available models: {len(models)})"
            else:
                health_status["ollama"] = f"unhealthy (HTTP {resp.status_code})"
    except Exception:
        health_status["ollama"] = "offline (check if ollama service is running)"

    return health_status
