"""
Standalone Runner for Jojira User Service Microservice (Port 8001).
"""

import sys
import uvicorn
from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware
from src.user_service.api.router import api_router

app = FastAPI(
    title="Jojira User Service Microservice",
    description="Dedicated microservice for Google OAuth, User Identity, Search History, & Saved Bookings.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
    from starlette.concurrency import iterate_in_threadpool

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace") if body_bytes else ""

    print("\n" + "=" * 85)
    print(f"[USER SERVICE REQUEST] {request.method} {request.url.path}")
    if body_str.strip():
        try:
            formatted_body = json.dumps(json.loads(body_str), indent=2)
            print(f"   Request Body:\n{formatted_body}")
        except Exception:
            print(f"   Request Body: {body_str}")
    else:
        print("   Request Body: (empty)")
    print("-" * 85)

    start_time = time.time()

    async def receive():
        return {"type": "http.request", "body": body_bytes}

    req_wrapped = Request(request.scope, receive=receive)
    response = await call_next(req_wrapped)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    response_body = [section async for section in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(response_body))
    res_bytes = b"".join(response_body)
    res_str = res_bytes.decode("utf-8", errors="replace") if res_bytes else ""

    print(f"[USER SERVICE RESPONSE] {request.method} {request.url.path} -> Status {response.status_code} (Total Execution Time: {duration_ms} ms)")
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
    print(f"   [TIMING] Request completed in {duration_ms} ms")
    print("=" * 85 + "\n")

    return response


app.include_router(api_router)



@app.get("/health", summary="Service Health Check", tags=["System"])
def health_check():
    return {"status": "healthy", "service": "jojira-user-service"}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8001))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    print(f"Starting Jojira User Service Microservice on http://0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
