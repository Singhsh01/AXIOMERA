"""Shared cache and rate limiting.

With ORKESTR_REDIS_URL set (as in Docker Compose), both are backed by Redis so every API worker
and replica shares the same counters and cached responses. Without it they fall back to
per-process memory, which is correct for a single worker (local development, tests).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)
_redis = None
_redis_checked = False
_lock = threading.Lock()
_mem: dict[str, tuple[float, Any]] = {}
_windows: dict[str, tuple[int, int]] = {}
_computing: set[str] = set()


def redis_client():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis

        r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5, decode_responses=True)
        r.ping()
        _redis = r
        log.info("cache and rate limiting use Redis")
    except Exception as e:  # noqa: BLE001
        log.warning("Redis unavailable (%s); falling back to in-process cache", e)
    return _redis


def cached(key: str, ttl: float, producer: Callable[[], Any]) -> Any:
    """Return a cached JSON-serialisable value, recomputed at most once per `ttl` seconds.

    Single-flight with stale-while-revalidate: when an entry expires, one caller takes a short
    lock and recomputes while concurrent callers keep receiving the previous value, so an expiry
    under heavy traffic triggers one database query instead of hundreds."""
    if not get_settings().cache_enabled:
        return producer()
    r = redis_client()
    if r is not None:
        try:
            raw = r.get(key)
            now = time.time()
            if raw is not None:
                entry = json.loads(raw)
                if entry["exp"] > now or not r.set(f"{key}:lock", "1", nx=True, px=int(max(ttl, 2) * 1000)):
                    return entry["v"]
            elif not r.set(f"{key}:lock", "1", nx=True, px=5000):
                # Someone else is computing a cold entry; wait briefly for it.
                for _ in range(40):
                    time.sleep(0.05)
                    raw = r.get(key)
                    if raw is not None:
                        return json.loads(raw)["v"]
            value = json.loads(json.dumps(producer(), default=str))
            r.set(key, json.dumps({"v": value, "exp": time.time() + ttl}), px=int(ttl * 20 * 1000))
            r.delete(f"{key}:lock")
            return value
        except Exception as e:  # noqa: BLE001  – never fail a request because the cache is down
            log.warning("cache error: %s", e)
            return producer()
    now = time.monotonic()
    with _lock:
        hit = _mem.get(key)
        if hit and (hit[0] > now or key in _computing):
            return hit[1]
        _computing.add(key)
    try:
        value = json.loads(json.dumps(producer(), default=str))
    finally:
        with _lock:
            _computing.discard(key)
    with _lock:
        _mem[key] = (now + ttl, value)
        if len(_mem) > 2000:
            for k in [k for k, (exp, _) in _mem.items() if exp <= now]:
                _mem.pop(k, None)
    return value


def invalidate(prefix: str) -> None:
    r = redis_client()
    if r is not None:
        try:
            for k in r.scan_iter(f"{prefix}*", count=200):
                r.delete(k)
        except Exception:  # noqa: BLE001
            pass
    with _lock:
        for k in [k for k in _mem if k.startswith(prefix)]:
            _mem.pop(k, None)


def hit_rate_limit(key: str, limit: int, window_s: int = 60) -> bool:
    """Fixed-window counter. Returns True when the caller is over the limit."""
    bucket = int(time.time() // window_s)
    r = redis_client()
    if r is not None:
        try:
            k = f"rl:{key}:{bucket}"
            n = r.incr(k)
            if n == 1:
                r.expire(k, window_s + 1)
            return n > limit
        except Exception:  # noqa: BLE001
            return False
    with _lock:
        b, n = _windows.get(key, (bucket, 0))
        n = n + 1 if b == bucket else 1
        _windows[key] = (bucket, n)
        if len(_windows) > 50_000:
            _windows.clear()
        return n > limit
