from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import api_router, admin_router
from app.db.session import init_db, engine
from app.services.mailcow import mailcow_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Debug mode: {settings.DEBUG}")

    # Initialize database (create tables if needed)
    # Note: In production, use Alembic migrations instead
    await init_db()

    # Check Mailcow connection
    if mailcow_service.is_configured:
        print(f"Mailcow API configured: {mailcow_service.api_url}")
        try:
            if await mailcow_service.health_check():
                print("Mailcow API connection: OK")
            else:
                print("Mailcow API connection: FAILED (service may be unavailable)")
        except Exception as e:
            print(f"Mailcow API connection: ERROR - {e}")
    else:
        print("Mailcow API: Not configured")

    yield

    # Shutdown
    print("Shutting down...")
    await mailcow_service.close()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Afrimail Backend API - Africa's Continental Email Platform",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}


# Include routers
# API routes (for user endpoints)
app.include_router(api_router, prefix="/api")

# Admin API routes
app.include_router(admin_router, prefix="/admin")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "Welcome to Afrimail API",
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
