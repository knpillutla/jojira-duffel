"""
FastAPI Application Initialization and Middleware Setup.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import router

from ..cli.parser import PromptParserTracker, prompt_parser_meta

logger = logging.getLogger("duffel.api")

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

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    message = str(detail)
    error_code = "REQUEST_ERROR"
    if "No Origin Found" in message or "origin" in message.lower():
        error_code = "NO_ORIGIN_FOUND"
        message = "No Origin Found. Please specify your departure origin city or airport in your query (e.g. 'Trip from Atlanta to Zurich') or include the X-User-Location header."
    elif "No Destination Found" in message or "destination" in message.lower():
        error_code = "NO_DESTINATION_FOUND"
        message = "No Destination Found. Please specify your travel destination in your query."

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error_code": error_code,
            "message": message,
            "detail": detail if isinstance(detail, (dict, list)) else str(detail),
            "path": str(request.url.path),
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid request parameter format. Please check required fields.",
            "detail": exc.errors(),
            "path": str(request.url.path),
        }
    )


@app.exception_handler(Exception)
async def global_generic_exception_handler(request: Request, exc: Exception):
    err_str = str(exc)
    error_code = "INTERNAL_SERVER_ERROR"
    status_code = 500

    if "No Origin Found" in err_str:
        error_code = "NO_ORIGIN_FOUND"
        status_code = 400
    elif "No Destination Found" in err_str:
        error_code = "NO_DESTINATION_FOUND"
        status_code = 400
    elif "LLM" in err_str or "OpenAI" in err_str:
        error_code = "LLM_EXECUTION_ERROR"
        status_code = 502
    elif "Duffel" in err_str or "duffel" in err_str.lower():
        error_code = "DUFFEL_API_ERROR"
        status_code = 502

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error_code": error_code,
            "message": err_str,
            "detail": err_str,
            "path": str(request.url.path),
        }
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
    prompt_parser_meta.set({})
    PromptParserTracker.clear()
    try:
        from ..timing import TimingTracker
        TimingTracker.reset()
    except Exception:
        pass

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

    res_bytes = b"".join(response_body)
    res_str = res_bytes.decode("utf-8", errors="replace") if res_bytes else ""

    if is_debug:
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

    meta = PromptParserTracker.get_latest() or prompt_parser_meta.get({})
    parser_engine = meta.get("engine", "N/A (Standard Request)")
    llm_used_flag = "YES" if meta.get("llm_used") else ("NO" if "engine" in meta else "N/A")
    extracted_json_val = meta.get("extracted_json")
    if extracted_json_val is not None:
        try:
            json_display = json.dumps(extracted_json_val)
        except Exception:
            json_display = str(extracted_json_val)
    else:
        json_display = "N/A"

    total_records_returned = 0
    res_json = None
    if res_str.strip():
        try:
            res_json = json.loads(res_str)
            if isinstance(res_json, dict):
                if "total_records" in res_json:
                    total_records_returned = _safe_int(res_json["total_records"])
                elif "total_results" in res_json:
                    total_records_returned = _safe_int(res_json["total_results"])
                elif "total_bundles_found" in res_json:
                    total_records_returned = _safe_int(res_json["total_bundles_found"])
                elif "total_offers_found" in res_json:
                    total_records_returned = _safe_int(res_json["total_offers_found"])
                elif "total_items" in res_json:
                    total_records_returned = _safe_int(res_json["total_items"])
                elif "data" in res_json and isinstance(res_json["data"], dict):
                    d = res_json["data"]
                    if "total_items" in d:
                        total_records_returned = _safe_int(d["total_items"])
                    elif "total_results" in d:
                        total_records_returned = _safe_int(d["total_results"])
                    elif "total_records" in d:
                        total_records_returned = _safe_int(d["total_records"])
                    elif "offers" in d and isinstance(d["offers"], list):
                        total_records_returned = len(d["offers"])
                    elif "results" in d and isinstance(d["results"], list):
                        total_records_returned = len(d["results"])
                    elif "top_bundles" in d and isinstance(d["top_bundles"], list):
                        total_records_returned = len(d["top_bundles"])
                elif "results" in res_json and isinstance(res_json["results"], list):
                    total_records_returned = len(res_json["results"])
                elif "offers" in res_json and isinstance(res_json["offers"], list):
                    total_records_returned = len(res_json["offers"])
                elif "top_offers" in res_json and isinstance(res_json["top_offers"], list):
                    total_records_returned = len(res_json["top_offers"])
                elif "top_bundles" in res_json and isinstance(res_json["top_bundles"], list):
                    total_records_returned = len(res_json["top_bundles"])
                elif "data" in res_json and isinstance(res_json["data"], list):
                    total_records_returned = len(res_json["data"])
            elif isinstance(res_json, list):
                total_records_returned = len(res_json)
        except Exception:
            pass

    t_metrics = None
    try:
        from ..timing import TimingTracker
        t_metrics = TimingTracker.get_metrics()
    except Exception:
        pass

    redis_read_ms = t_metrics.redis_read_ms if t_metrics else 0.0
    redis_write_ms = t_metrics.redis_write_ms if t_metrics else 0.0
    llm_ms = t_metrics.llm_execution_ms if t_metrics else 0.0
    duffel_api_ms = t_metrics.duffel_api_ms if t_metrics else 0.0
    tracked_subtotal = redis_read_ms + redis_write_ms + llm_ms + duffel_api_ms
    algo_ms = max(0.0, duration_ms - tracked_subtotal)

    # Extract Service Execution Summary & Provenance details from response or metadata
    service_exec = None
    if isinstance(res_json, dict):
        if "service_execution_summary" in res_json and isinstance(res_json["service_execution_summary"], dict):
            service_exec = res_json["service_execution_summary"]
        elif "meta_data" in res_json and isinstance(res_json["meta_data"], dict) and "service_execution_summary" in res_json["meta_data"]:
            service_exec = res_json["meta_data"]["service_execution_summary"]
        elif "data" in res_json and isinstance(res_json["data"], dict):
            d = res_json["data"]
            if "trip_summary" in d and isinstance(d["trip_summary"], dict) and "service_execution_summary" in d["trip_summary"]:
                service_exec = d["trip_summary"]["service_execution_summary"]
            elif "service_execution_summary" in d:
                service_exec = d["service_execution_summary"]

    flight_calls_disp = "N/A"
    hotel_calls_disp = "N/A"
    car_calls_disp = "N/A"
    itinerary_synth_disp = "N/A"
    prompt_eval_disp = f"Live LLM ({parser_engine})" if meta.get("llm_used") else f"Deterministic Regex Heuristics ({parser_engine})"

    if service_exec and isinstance(service_exec, dict):
        # Prompt evaluation details
        p_eval = service_exec.get("prompt_evaluation") or {}
        if p_eval:
            is_p_llm = p_eval.get("is_llm", meta.get("llm_used", False))
            p_eng = p_eval.get("engine", parser_engine)
            prompt_eval_disp = f"Live LLM ({p_eng})" if is_p_llm else f"Deterministic Regex Heuristics ({p_eng})"

        # Itinerary synthesis details
        itin_info = service_exec.get("itinerary_planner") or {}
        if itin_info:
            if itin_info.get("is_live_llm") or not itin_info.get("is_synthetic"):
                itinerary_synth_disp = f"Live LLM ({itin_info.get('llm_provider', 'openai')} - {itin_info.get('llm_model', 'gpt-4o-mini')})"
            else:
                itinerary_synth_disp = f"Synthetic Template Synthesizer ({itin_info.get('llm_model', 'template-engine-v1')})"

        # Component service calls & data sources
        cds = service_exec.get("component_data_sources") or {}
        sc = service_exec.get("service_calls") or {}

        fl_ds = cds.get("flights") or {}
        ht_ds = cds.get("hotels") or {}
        cr_ds = cds.get("cars") or {}

        fl_calls = fl_ds.get("calls_made", sc.get("flight_calls_count", 0))
        ht_calls = ht_ds.get("calls_made", sc.get("hotel_calls_count", 0))
        cr_calls = cr_ds.get("calls_made", sc.get("car_calls_count", 0))

        fl_synth = fl_ds.get("is_synthetic", False)
        ht_synth = ht_ds.get("is_synthetic", False)
        cr_synth = cr_ds.get("is_synthetic", False)

        flight_calls_disp = f"{fl_calls} ({'Synthetic Mock Data' if fl_synth else 'Live Duffel API'})"
        hotel_calls_disp = f"{ht_calls} ({'Synthetic Mock Data' if ht_synth else 'Live Duffel API'})"
        car_calls_disp = f"{cr_calls} ({'Synthetic Mock Data' if cr_synth else 'Live Duffel API'})"
    elif isinstance(res_json, dict) and "meta_data" in res_json and isinstance(res_json["meta_data"], dict) and "data_source" in res_json["meta_data"]:
        ds = res_json["meta_data"]["data_source"]
        fl_calls = ds.get("flight_calls_count", 0)
        ht_calls = ds.get("hotel_calls_count", 0)
        cr_calls = ds.get("car_calls_count", 0)
        fl_synth = ds.get("is_flights_synthetic", False)
        ht_synth = ds.get("is_hotels_synthetic", False)
        cr_synth = ds.get("is_cars_synthetic", False)

        flight_calls_disp = f"{fl_calls} ({'Synthetic Mock Data' if fl_synth else 'Live Duffel API'})"
        hotel_calls_disp = f"{ht_calls} ({'Synthetic Mock Data' if ht_synth else 'Live Duffel API'})"
        car_calls_disp = f"{cr_calls} ({'Synthetic Mock Data' if cr_synth else 'Live Duffel API'})"

        if ds.get("is_live_llm"):
            itinerary_synth_disp = f"Live LLM ({ds.get('llm_provider', 'openai')} - {ds.get('llm_model', 'gpt-4o-mini')})"
        else:
            itinerary_synth_disp = "Synthetic Template Synthesizer"

        if ds.get("prompt_evaluation_source") == "live_llm" or not ds.get("is_prompt_evaluation_synthetic"):
            prompt_eval_disp = f"Live LLM ({parser_engine})"
        else:
            prompt_eval_disp = f"Deterministic Regex Heuristics ({parser_engine})"

    # Print clean INFO-level request/response cycle summary box
    print("\n" + "=" * 85, flush=True)
    print(f"[REST REQUEST SUMMARY] {request.method} {request.url.path}", flush=True)
    print(f"  * URL                       : {request.url}", flush=True)
    print(f"  * Request Received Time      : {req_start_str}", flush=True)
    print(f"  * Response Sent Time        : {req_end_str}", flush=True)
    print(f"  * Total Execution Time      : {duration_ms} ms ({duration_sec}s)", flush=True)
    print(f"  --- DETAILED TIME BREAKDOWN (PERFORMANCE METRICS) ---", flush=True)
    print(f"  * Redis Cache Read Time     : {redis_read_ms:.2f} ms", flush=True)
    print(f"  * Redis Cache Write Time    : {redis_write_ms:.2f} ms", flush=True)
    print(f"  * LLM Execution Time        : {llm_ms:.2f} ms", flush=True)
    print(f"  * Duffel API Call Time      : {duffel_api_ms:.2f} ms", flush=True)
    print(f"  * Algorithm & Synthesis Time: {algo_ms:.2f} ms", flush=True)
    print(f"  -----------------------------------------------------", flush=True)
    print(f"  * Prompt Input Extraction   : {prompt_eval_disp}", flush=True)
    print(f"  * Prompt Parser Engine      : {parser_engine}", flush=True)
    print(f"  * LLM Used Evaluator        : {llm_used_flag}", flush=True)
    print(f"  * Extracted Intent JSON     : {json_display}", flush=True)
    is_planner_or_bundle = any(k in str(request.url.path).lower() for k in ["planner", "bundle", "search", "itinerary"])
    if is_planner_or_bundle or flight_calls_disp != "N/A" or hotel_calls_disp != "N/A" or car_calls_disp != "N/A" or itinerary_synth_disp != "N/A":
        print(f"  * Itinerary Schedule Engine : {itinerary_synth_disp if itinerary_synth_disp != 'N/A' else 'Synthetic Template Synthesizer'}", flush=True)
        print(f"  * Duffel Flight API Calls   : {flight_calls_disp if flight_calls_disp != 'N/A' else '0 (No Calls)'}", flush=True)
        print(f"  * Duffel Hotel API Calls    : {hotel_calls_disp if hotel_calls_disp != 'N/A' else '0 (No Calls)'}", flush=True)
        print(f"  * Duffel Car API Calls      : {car_calls_disp if car_calls_disp != 'N/A' else '0 (No Calls)'}", flush=True)
    print(f"  * Total Duffel API Calls    : {api_calls}", flush=True)
    print(f"  * Delayed Calls (429 Limit) : {delayed_calls}", flush=True)
    print(f"  * Cache Hit Status          : {cache_hit_str}", flush=True)
    print(f"  * Records Retrieved Cache   : {records_retrieved}", flush=True)
    print(f"  * Records Written Cache     : {records_written}", flush=True)
    print(f"  * Total Records Returned    : {total_records_returned}", flush=True)
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
