from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    APIProblem,
    handle_api_problem,
    handle_http_error,
    handle_unexpected_error,
    handle_validation_error,
)
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from fastapi.exceptions import RequestValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knexus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing KNEXUS Backend...")
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

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )


@app.middleware("http")
async def request_correlation_id(request: Request, call_next):
    request_id = uuid4()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = str(request_id)
    return response


app.add_exception_handler(APIProblem, handle_api_problem)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.add_exception_handler(StarletteHTTPException, handle_http_error)
app.add_exception_handler(Exception, handle_unexpected_error)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to the KNEXUS API",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }
