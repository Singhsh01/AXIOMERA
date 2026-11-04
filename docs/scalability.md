# Scalability and load testing

The goal is many concurrent customers without the API or the database falling over. Overload has to degrade into slower or briefly refused requests, never into deadlocks or crashes.

## What protects the server

| Layer | Mechanism | Where |
|---|---|---|
| Edge of the API | Per-user rate limit (`AXIOMERA_RATE_LIMIT_PER_MINUTE`, default 600). Keyed on the signed-in user, not the proxy IP, so one busy tab cannot throttle everyone behind the web proxy | `app/main.py` |
| Login | 30 attempts/min per IP, 10/min per e-mail, 5-failure lockout for 15 min, every attempt recorded | `app/routers/auth.py` |
| Admission control | At most `db_pool_size - 2` API requests run at once per worker; the rest wait up to 8 s, then get `503 Retry-After: 2` | `app/main.py` |
| Read cache | Single-flight, stale-while-revalidate cache in Redis: one request per key recomputes and the others get the last value. Dashboards and lists are computed about once per TTL per workspace, not once per viewer | `app/core/cache.py` |
| Database | Sized pool (`pool_size` + `max_overflow` per worker, `pool_recycle`), Postgres `max_connections=120`, indexes on every polled `(workspace, status/created_at)` filter, eager loading on the case list (no N+1) | `app/db.py`, migration `0002` |
| Transport | gzip for responses >1 KB, `uvicorn[standard]` (httptools/uvloop), several workers | `Dockerfile`, compose |

Why admission control matters: FastAPI runs sync endpoints in a 40-thread pool, but each worker only has 20 DB connections. Before the fix, 500+ simultaneous users filled the threads, exhausted the pool, and requests timed out holding connections "idle in transaction". The semaphore caps in-flight work below the pool size, so overload turns into queueing or a clean 503.

## Measured results

Tool: `scripts/loadtest.py`. It creates N viewer accounts and each virtual user polls what an open browser tab polls (dashboard, notifications, cases, approvals, analytics, workflows) every 1.5–3 s, using several client processes. Raw output is in `docs/loadtest/`.

Environment: a single 2-vCPU sandbox running Postgres, Redis, the API (2 workers) **and the load generator together**.

| Concurrent users | Requests | Success | p50 | p95 | p99 |
|---|---|---|---|---|---|
| 250 (before fixes) | 4,251 | 100 % | 65 ms | 205 ms | 435 ms |
| 500 (before fixes) | — | **31 %** (timeouts, pool exhaustion) | — | — | — |
| 1,000 (before fixes) | — | **0 %** | — | — | — |
| 500 (after) | 9,847 | **100 %** | 17 ms | 48–84 ms | 224 ms |
| 1,000 (after) | 7,691 | **99.9 %** | 2.8 s | 8.3 s | 10.6 s |
| 2,000 (after) | 9,885 | **99.9 %** | 5.0 s | 22 s | 34 s |

How to read the 1,000 and 2,000 rows: during those runs the load-generator processes used about 1.4 of the 2 vCPUs, leaving the API about 0.45 of a core. Those numbers show **CPU starvation in the test box degrading gracefully**: no crashes, no pool exhaustion, and the 0.1 % errors are client-side connection resets. They do not show the API's ceiling.

The number that transfers to real hardware is the measured cost per request: **4.4 ms of API CPU per request, with negligible Postgres CPU** (the cache absorbs the reads). That is about 225 requests/s per API core. A user with the app open generates about 0.45 requests/s, so:

| API cores (workers × replicas) | Concurrently active users (approx.) |
|---|---|
| 2 | ~1,000 |
| 4 | ~2,000 |
| 8 | ~4,000 |

"Customers" are usually far more than concurrently active users, so a few thousand customers fit on a modest host. These are estimates from the per-request cost, not a measurement on production hardware. Re-run the load test on your target hardware with the generator on a separate machine before relying on them.

## Scaling out

The API is stateless: state lives in Postgres and limits and cache in Redis. To scale:
1. Raise `WEB_CONCURRENCY` to about the number of cores.
2. Keep `WEB_CONCURRENCY × (AXIOMERA_DB_POOL_SIZE + max_overflow)` below Postgres `max_connections` (120). Beyond that, put PgBouncer in front of Postgres.
3. Run more API replicas behind a load balancer, all pointing at the same Postgres and Redis.

Prometheus metrics at `/metrics` are per worker process. Aggregate them in Prometheus, or use the multiprocess mode of `prometheus_client` if you need one scrape per host.

## Reproduce

```bash
cd backend && pip install -r requirements.txt
export AXIOMERA_DATABASE_URL=postgresql+psycopg://axiomera:axiomera@localhost:5433/axiomera   # the compose Postgres
python ../scripts/loadtest.py --users 500 --duration 45 --base http://localhost:8000
python ../scripts/loadtest.py --cleanup
```
