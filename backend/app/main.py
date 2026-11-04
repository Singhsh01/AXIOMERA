from __future__ import annotations

import logging
import time
import asyncio
import hashlib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.core import naming
from app.core.naming import LEGACY_SESSION_COOKIE, SESSION_COOKIE
from app.core.cache import hit_rate_limit
from app.core.observability import HTTP_LATENCY, HTTP_REQUESTS, REGISTRY, configure_logging, correlation_id_var, setup_tracing
from app.db import get_engine, new_id
from app.platform import workflows
from app.routers import auth, knowledge, ops, platform, rfp

import app.agents.tools  # noqa: F401  (registers tools)

configure_logging()
log = logging.getLogger("axiomera")
settings = get_settings()

app = FastAPI(
    title="Axiomera API",
    version="0.1.0",
    description="Autonomous enterprise operations & proposal intelligence. n8n orchestrates; this API is the source of truth.",
    openapi_tags=[{"name": t} for t in ["auth", "operations", "proposals", "knowledge", "platform"]],
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)


def _client_key(request: Request) -> str:
    """Rate-limit per signed-in user when possible. Browser traffic arrives through the web
    proxy, so the TCP peer is the proxy for everyone; the session token (or forwarded IP) is not."""
    # Same precedence as authentication (deps.get_principal): Authorization header, then cookie.
    token = request.headers.get("authorization", "") or request.cookies.get(SESSION_COOKIE) or request.cookies.get(LEGACY_SESSION_COOKIE)
    if token:
        return "t:" + hashlib.sha256(token.encode()).hexdigest()[:24]
    fwd = request.headers.get("x-forwarded-for")
    return "ip:" + (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "anon"))


# Admission control. Endpoints are synchronous and take a pooled DB connection during
# authentication; without a cap, a burst fills the thread pool with requests waiting for a
# connection while connection holders wait for a thread (deadlock until timeouts). Keeping
# in-flight API requests per worker below the pool size makes overload queue briefly and then
# shed with 503 + Retry-After instead of hanging.
_inflight = asyncio.Semaphore(max(2, settings.db_pool_size - 2))
ADMISSION_WAIT_S = 8.0


@app.middleware("http")
async def admission_control(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    try:
        await asyncio.wait_for(_inflight.acquire(), timeout=ADMISSION_WAIT_S)
    except TimeoutError:
        return JSONResponse({"detail": "Server busy, please retry"}, status_code=503, headers={"Retry-After": "2"})
    try:
        return await call_next(request)
    finally:
        _inflight.release()


@app.middleware("http")
async def platform_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or new_id()
    correlation_id_var.set(cid[:64])
    # Rate limiting (sliding window per client). Service calls from n8n are exempt.
    if request.url.path.startswith("/api/") and naming.header(request.headers, "Service-Token") is None:
        if hit_rate_limit(_client_key(request), settings.rate_limit_per_minute):
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"})
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


naming.warn_legacy_env(log)
