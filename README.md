# Jajira LLC Duffel Travel Platform

This repository contains the production-ready travel API layer for flight search and booking. It wraps the Duffel API with a modular FastAPI service, tiered caching, optimized multi-day search logic, and exportable JSON outputs that power the customer-facing web UI.

## Included capabilities

- Flight search with flexible multi-day optimization
- Category ranking for cheapest, shortest, non-stop, 1-stop, and favorite-airline options
- Redis-backed cache layer with metrics and fallback behavior
- Booking flow contract for offer purchase requests
- JSON export of search results for downstream analytics and UI caching
- Docker deployment support for production hosting

## Local development

```bash
cd C:/neel/personal/projects/jajirallc-duffel
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python run_api.py --host 127.0.0.1 --port 8000
```

Then browse to:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/api/v1/health

## Docker

```bash
docker build -t jajira-duffel-api .
docker run --rm -p 8000:8000 -e DUFFEL_API_TOKEN=your_token jajira-duffel-api
```

The UI project in `../jajirallc-duffel-ui` serves the customer frontend and proxies `/api` requests to this service.
