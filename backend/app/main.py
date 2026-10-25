import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings, enforce_production_safety
from app.database.session import init_db, engine
from app.api import auth, invoices, ocr, dashboard, admin, agent
from app.services.cloud_storage_service import cloud_storage_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("invoshield")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting InvoShield AI backend service...")
    # Hard stop (not just a log line) if production is running with default secrets.
    enforce_production_safety(settings)
    try:
        init_db()
        logger.info("Database schema initialized and seed accounts verified.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
    yield
    logger.info("Shutting down InvoShield AI backend service.")

app = FastAPI(
    title="InvoShield AI API",
    description="Secure AI-Based Automated Invoice Processing and Validation System Using OCR, RapidFuzz, AES Encryption, and Cloud Computing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    # "*" is a development convenience only; production uses the explicit origin list.
    allow_origins=[o for o in settings.CORS_ORIGINS if not (settings.is_production and o == "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError

# Request validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"422 Validation Error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred. Please check system logs."}
    )

# Routers
app.include_router(auth.router)
app.include_router(invoices.router)
app.include_router(ocr.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(agent.router)

@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint verifying DB connection and storage state."""
    db_ok = True
    try:
        with engine.connect():
            pass
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database_connected": db_ok,
        "s3_cloud_available": cloud_storage_service._s3_available,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to InvoShield AI API",
        "docs_url": "/docs",
        "health_check": "/api/health"
    }
