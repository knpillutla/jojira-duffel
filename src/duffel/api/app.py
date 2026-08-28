"""
FastAPI Application Initialization and Middleware Setup.
"""

from typing import Any

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
    import time
    from datetime import datetime
    from starlette.concurrency import iterate_in_threadpool

    req_start_dt = datetime.now()
    req_start_str = req_start_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    t0 = time.time()

    # Reset per-request metrics on shared DuffelClient instance
    client = None
    try:
        from .routes.common import get_duffel_client
        client = get_duffel_client()
        if hasattr(client, "http_client") and client.http_client:
            client.http_client.reset_request_stats()
        if hasattr(client, "cache") and client.cache:
            client.cache.reset_request_stats()
    except Exception:
        client = None

    is_debug = False
    if client and hasattr(client, "config") and client.config:
        is_debug = bool(getattr(client.config, "debug", False) or getattr(client.config, "debug_mode", False))

    # Log request arrival immediately upon receiving
    print(f"[REST REQUEST RECEIVED] {request.method} {request.url.path} | Time: {req_start_str}", flush=True)
    logger.info("[REST REQUEST RECEIVED] %s %s | Time: %s", request.method, request.url.path, req_start_str)

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

    if is_debug:
        print("\n" + "=" * 85, flush=True)
        print(f"[REST DEBUG REQUEST] {request.method} {request.url.path}", flush=True)
        print(f"   Request Received Time: {req_start_str}", flush=True)
        if body_str.strip():
            try:
                formatted_body = json.dumps(json.loads(body_str), indent=2)
                print(f"   Request Body:\n{formatted_body}", flush=True)
            except Exception:
                print(f"   Request Body: {body_str}", flush=True)
        print("-" * 85, flush=True)

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    req_wrapped = Request(request.scope, receive=receive)
    response = await call_next(req_wrapped)
    
    t1 = time.time()
    req_end_dt = datetime.now()
    req_end_str = req_end_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    duration_ms = round((t1 - t0) * 1000, 2)
    duration_sec = round(t1 - t0, 3)

    response_body = [section async for section in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(response_body))

    if is_debug:
        res_bytes = b"".join(response_body)
        res_str = res_bytes.decode("utf-8", errors="replace") if res_bytes else ""
        print(f"[REST DEBUG RESPONSE] {request.method} {request.url.path} -> Status {response.status_code} ({duration_ms} ms)")
        if res_str.strip():
            try:
                formatted_res = json.dumps(json.loads(res_str), indent=2)
                print(f"   Response Body:\n{formatted_res[:1000]}...")
            except Exception:
                print(f"   Response Body: {res_str[:500]}")

    def _safe_int(val: Any) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return 0

    api_calls = 0
    delayed_calls = 0
    cache_hit_str = "NO"
    records_retrieved = 0
    records_written = 0

    if client:
        if hasattr(client, "http_client") and client.http_client:
            try:
                h_stats = client.http_client.get_request_stats()
                if isinstance(h_stats, dict):
                    api_calls = _safe_int(h_stats.get("api_calls", 0))
                    delayed_calls = _safe_int(h_stats.get("delayed_calls", 0))
            except Exception:
                pass
        if hasattr(client, "cache") and client.cache:
            try:
                c_stats = client.cache.get_request_stats()
                if isinstance(c_stats, dict):
                    cache_hit_str = "YES" if c_stats.get("cache_hit") else "NO"
                    records_retrieved = _safe_int(c_stats.get("records_retrieved", 0))
                    records_written = _safe_int(c_stats.get("records_written", 0))
            except Exception:
                pass

    # Print clean INFO-level request/response cycle summary box
    print("\n" + "=" * 85, flush=True)
    print(f"[REST REQUEST SUMMARY] {request.method} {request.url.path}", flush=True)
    print(f"  * URL                       : {request.url}", flush=True)
    print(f"  * Request Received Time      : {req_start_str}", flush=True)
    print(f"  * Response Sent Time        : {req_end_str}", flush=True)
    print(f"  * Total Execution Time      : {duration_ms} ms ({duration_sec}s)", flush=True)
    print(f"  * Duffel API Calls Made     : {api_calls}", flush=True)
    print(f"  * Delayed Calls (429 Limit) : {delayed_calls}", flush=True)
    print(f"  * Cache Hit Status          : {cache_hit_str}", flush=True)
    print(f"  * Records Retrieved Cache   : {records_retrieved}", flush=True)
    print(f"  * Records Written Cache     : {records_written}", flush=True)
    print(f"  * HTTP Status Code          : {response.status_code}", flush=True)
    print("=" * 85 + "\n", flush=True)

    return response

# Include API Router for /api/v1, /api, and root path compatibility
app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api", include_in_schema=False)
app.include_router(router, include_in_schema=False)

# Include User Service Microservice Router
try:
    from user_service.api.router import api_router as user_service_router
    app.include_router(user_service_router)
except Exception:
    try:
        from src.user_service.api.router import api_router as user_service_router
        app.include_router(user_service_router)
    except Exception as us_err:
        print(f"[APP NOTICE] User service router notice: {us_err}")




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
