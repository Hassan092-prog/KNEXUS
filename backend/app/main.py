from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knexus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing KNEXUS Backend...")
    # Any startup actions (e.g. checking models, extensions)
    yield
    logger.info("Shutting down KNEXUS Backend...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Knowledge Network for Exploration and Unified Services API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware setup
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to the KNEXUS API",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }
