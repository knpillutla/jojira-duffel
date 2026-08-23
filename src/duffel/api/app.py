"""
FastAPI Application Initialization and Middleware Setup.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import router

app = FastAPI(
    title="Jajira LLC - Duffel Flight REST API",
    description="High-performance REST API web service for Duffel Flight Search, 2-Tier Caching Optimization, Non-Stop Ranking, and Order Booking.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS Middleware for cross-origin web frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive OpenAPI docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", summary="System Health Check (Root Alias)", tags=["System"])
def root_health_check():
    """System health check endpoint at root level."""
    from .routes import health_check
    return health_check()


@app.get("/help", summary="API Help & Documentation Index (Root Alias)", tags=["System"])
def root_api_help(request: Request):
    """API documentation and schema index endpoint at root level."""
    from .routes import get_api_help
    return get_api_help(request)
