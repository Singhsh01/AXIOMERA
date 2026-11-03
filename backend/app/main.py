from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.core.observability import HTTP_LATENCY, HTTP_REQUESTS, REGISTRY, configure_logging, correlation_id_var, setup_tracing
from app.db import get_engine, new_id
from app.platform import workflows
from app.routers import auth, knowledge, ops, platform, rfp

import app.agents.tools  # noqa: F401  (registers tools)

configure_logging()
log = logging.getLogger("orkestr")
settings = get_settings()

app = FastAPI(
    title="Orkestr API",
    version="0.1.0",
    description="Autonomous enterprise operations & proposal intelligence. n8n orchestrates; this API is the source of truth.",
    openapi_tags=[{"name": t} for t in ["auth", "operations", "proposals", "knowledge", "platform"]],
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_buckets: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def platform_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or new_id()
    correlation_id_var.set(cid[:64])
    # Rate limiting (sliding window per client). Service calls from n8n are exempt.
    if request.url.path.startswith("/api/") and "x-orkestr-service-token" not in request.headers:
        key = request.headers.get("authorization", "")[-24:] or (request.client.host if request.client else "anon")
        q, now = _buckets[key], time.monotonic()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"})
        q.append(now)
    t0 = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    HTTP_LATENCY.labels(path).observe(time.perf_counter() - t0)
    response.headers["X-Correlation-Id"] = cid
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


API = "/api/v1"
for r in (auth.router, ops.router, rfp.router, knowledge.router, platform.router):
    app.include_router(r, prefix=API)


@app.get("/health", tags=["platform"])
def health():
    db_ok = True
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "n8n": workflows.n8n_health(), "llm_provider": settings.llm_provider}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


if settings.otel_enabled:
    setup_tracing(app, settings.otel_endpoint)
