#!/usr/bin/env python3
"""Load test that behaves like people using the web app.

Each virtual user has its own account and session token and repeats what the UI does while a
page is open: poll the command-center summary, notifications, open cases and pending approvals,
and occasionally analytics and the workflow list, with 1.5–3 s of think time between requests.

    cd backend && python ../scripts/loadtest.py --users 500 --duration 45
    python ../scripts/loadtest.py --users 1000 --duration 45 --base http://localhost:8000

Accounts are created as `viewer` users named loadtest-NNNN@axiomera.dev (read-only) and tokens are
minted directly, so the run is not throttled by the login rate limit. --cleanup removes them.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402

ENDPOINTS = [  # (path, weight) — mirrors the polling intervals of the UI pages
    ("/api/v1/dashboard/summary", 5),
    ("/api/v1/notifications", 3),
    ("/api/v1/cases?status=open", 2),
    ("/api/v1/approvals?status=pending", 2),
    ("/api/v1/analytics/overview?days=14", 1),
    ("/api/v1/workflows", 1),
]


def prepare_users(n: int) -> list[str]:
    from sqlalchemy import select

    from app.core.security import create_token, hash_password
    from app.db import session_factory
    from app.models import Organization, User, Workspace, WorkspaceMember

    db = session_factory()()
    org = db.scalars(select(Organization).where(Organization.slug == "helix-ridge")).one()
    ws = db.scalars(select(Workspace).where(Workspace.org_id == org.id)).first()
    existing = {u.email: u for u in db.scalars(select(User).where(User.email.like("loadtest-%@axiomera.dev")))}
    pw = hash_password("loadtest-not-for-login")
    tokens = []
    for i in range(n):
        email = f"loadtest-{i:04d}@axiomera.dev"
        u = existing.get(email)
        if u is None:
            u = User(org_id=org.id, email=email, name=f"Load {i}", role="viewer", password_hash=pw)
            db.add(u)
            db.flush()
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id))
        tokens.append(create_token(u.id, org.id, "viewer"))
    db.commit()
    db.close()
    return tokens


def cleanup() -> None:
    from sqlalchemy import delete, select

    from app.db import session_factory
    from app.models import User, WorkspaceMember

    db = session_factory()()
    ids = [u.id for u in db.scalars(select(User).where(User.email.like("loadtest-%@axiomera.dev")))]
    db.execute(delete(WorkspaceMember).where(WorkspaceMember.user_id.in_(ids)))
    db.execute(delete(User).where(User.id.in_(ids)))
    db.commit()
    print(f"removed {len(ids)} load-test users")


async def virtual_user(client: httpx.AsyncClient, token: str, stop_at: float, lat: dict, codes: Counter):
    paths = [p for p, w in ENDPOINTS for _ in range(w)]
    await asyncio.sleep(random.uniform(0, 3))  # ramp-up
    while time.monotonic() < stop_at:
        path = random.choice(paths)
        t0 = time.perf_counter()
        try:
            r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
            codes[r.status_code] += 1
        except Exception as e:  # noqa: BLE001
            codes[type(e).__name__] += 1
        lat[path.split("?")[0]].append((time.perf_counter() - t0) * 1000)
        await asyncio.sleep(random.uniform(1.5, 3.0))


async def _drive(base: str, tokens: list[str], duration: int):
    lat: dict[str, list[float]] = defaultdict(list)
    codes: Counter = Counter()
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=400)
    async with httpx.AsyncClient(base_url=base, timeout=30, limits=limits) as client:
        stop_at = time.monotonic() + duration
        await asyncio.gather(*(virtual_user(client, t, stop_at, lat, codes) for t in tokens))
    return dict(lat), dict(codes)


def _proc(args):
    base, tokens, duration = args
    return asyncio.run(_drive(base, tokens, duration))


def run(base: str, users: int, duration: int, procs: int) -> dict:
    """Virtual users are spread over several client processes so the generator itself is not the bottleneck."""
    from multiprocessing import Pool

    tokens = prepare_users(users)
    chunks = [tokens[i::procs] for i in range(procs)]
    t0 = time.monotonic()
    with Pool(procs) as pool:
        parts = pool.map(_proc, [(base, c, duration) for c in chunks if c])
    elapsed = time.monotonic() - t0
    lat: dict[str, list[float]] = defaultdict(list)
    codes: Counter = Counter()
    for l, c in parts:
        for k, v in l.items():
            lat[k].extend(v)
        codes.update(c)
    allv = sorted(v for vs in lat.values() for v in vs)
    q = lambda xs, p: xs[min(len(xs) - 1, int(len(xs) * p))] if xs else None  # noqa: E731
    total = sum(codes.values())
    ok = sum(n for c, n in codes.items() if c == 200)
    return {
        "users": users, "client_processes": procs, "duration_s": round(elapsed, 1), "requests": total,
        "throughput_rps": round(total / elapsed, 1),
        "success_rate": round(100 * ok / total, 2) if total else None, "status_codes": {str(k): v for k, v in codes.items()},
        "p50_ms": round(q(allv, 0.5), 1), "p95_ms": round(q(allv, 0.95), 1), "p99_ms": round(q(allv, 0.99), 1),
        "per_endpoint_p95_ms": {k: round(q(sorted(v), 0.95), 1) for k, v in sorted(lat.items())},
        "mean_ms": round(statistics.mean(allv), 1),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("API_URL", "http://localhost:8000"))
    ap.add_argument("--users", type=int, default=200)
    ap.add_argument("--duration", type=int, default=45)
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--cleanup", action="store_true")
    a = ap.parse_args()
    if a.cleanup:
        cleanup()
    else:
        import json

        print(json.dumps(run(a.base, a.users, a.duration, a.procs), indent=2))
