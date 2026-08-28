"""
Executable script to launch the Duffel REST API Web Server.
Usage: python run_api.py [--host HOST] [--port PORT]
"""

import sys
import uvicorn

def main():
    import os
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))

    if "--host" in sys.argv:
        try:
            idx = sys.argv.index("--host")
            host = sys.argv[idx + 1]
        except (IndexError, ValueError):
            pass

    if "--port" in sys.argv:
        try:
            idx = sys.argv.index("--port")
            port = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            pass

    print("\n=================================================================")
    print("      JAJIRA LLC - DUFFEL REST API WEB SERVER (FASTAPI)          ")
    print("=================================================================")
    print(f"  * Server URL              : http://{host}:{port}")
    print(f"  * OpenAPI Interactive Docs: http://{host}:{port}/docs")
    print(f"  * ReDoc API Docs          : http://{host}:{port}/redoc")
    print(f"  * Health Check            : http://{host}:{port}/api/v1/health")
    print("=================================================================\n")

    uvicorn.run("src.duffel.api.app:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    main()
