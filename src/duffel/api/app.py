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


@app.middleware("http")
async def log_requests_and_responses(request: Request, call_next):
    import json
    from starlette.concurrency import iterate_in_threadpool

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

    print("\n" + "=" * 85)
    print(f"[REST REQUEST] {request.method} {request.url.path}")
    if body_str.strip():
        try:
            formatted_body = json.dumps(json.loads(body_str), indent=2)
            print(f"   Request Body:\n{formatted_body}")
        except Exception:
            print(f"   Request Body: {body_str}")
    else:
        print("   Request Body: (empty)")
    print("-" * 85)

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    req_wrapped = Request(request.scope, receive=receive)
    response = await call_next(req_wrapped)

    response_body = [section async for section in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(response_body))
    res_bytes = b"".join(response_body)
    res_str = res_bytes.decode("utf-8", errors="replace") if res_bytes else ""

    print(f"[REST RESPONSE] {request.method} {request.url.path} -> Status {response.status_code}")
    if res_str.strip():
        try:
            formatted_res = json.dumps(json.loads(res_str), indent=2)
            if len(formatted_res) > 2000:
                print(f"   Response Body (Truncated):\n{formatted_res[:2000]}...\n[Total length: {len(formatted_res)} chars]")
            else:
                print(f"   Response Body:\n{formatted_res}")
        except Exception:
            print(f"   Response Body: {res_str[:1000]}")
    else:
        print("   Response Body: (empty)")
    print("=" * 85 + "\n")

    return response

# Include API Router for /api/v1, /api, and root path compatibility
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api", include_in_schema=False)
app.include_router(router, include_in_schema=False)


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
