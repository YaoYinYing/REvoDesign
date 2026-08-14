# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Rate limiter for sensitive endpoints.

Uses a Redis fixed window keyed by ``{module}.{qualname}:{ip}`` shared
across gunicorn workers when Redis is available.  When Redis is down, falls
back to the in-memory per-worker limiter (documented: not distributed).
Availability beats strictness — a Redis outage degrades, never breaks,
the endpoints.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import jsonify, request
from revocompute.redis_util import get_redis


def rate_limit(max_requests: int, window_seconds: int):
    """Decorator: allow at most *max_requests* per *window_seconds* per IP.

    Usage::

        @app.route("/login", methods=["POST"])
        @rate_limit(max_requests=5, window_seconds=60)
        def login():
            ...
    """
    # In-memory fallback state — only used when Redis is unavailable.
    state: dict[str, list[float]] = {}
    _lock = threading.Lock()
    _last_cleanup: float = time.monotonic()

    def _prune_expired(cutoff: float) -> None:
        """Drop per-IP entries whose most recent timestamp is expired."""
        empty = [ip for ip, ts in state.items() if not ts or ts[-1] <= cutoff]
        for ip in empty:
            del state[ip]

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            nonlocal _last_cleanup
            # Forwarded-IP headers are useful for audit metadata but are not a
            # trustworthy limiter key: clients can spoof them unless every
            # request is guaranteed to traverse a trusted proxy. The socket
            # peer cannot be changed by an HTTP header.
            ip = request.remote_addr or "unknown"
            now = time.monotonic()
            cutoff = now - window_seconds

            redis_client = get_redis()
            if redis_client is not None:
                # Redis fixed window: INCR, set TTL on first hit, reject past
                # the limit with the remaining TTL as retry_after.
                key = f"{f.__module__}.{f.__qualname__}:{ip}"
                try:
                    count = redis_client.incr(key)
                    if count == 1:
                        if not redis_client.expire(key, window_seconds):
                            if redis_client.ttl(key) == -1:
                                redis_client.expire(key, window_seconds)
                    if count > max_requests:
                        ttl = redis_client.ttl(key)
                        retry_after = int(ttl) if ttl > 0 else window_seconds
                        return (
                            jsonify(
                                {
                                    "error": "Too many requests",
                                    "retry_after_seconds": max(retry_after, 1),
                                }
                            ),
                            429,
                        )
                except Exception:
                    # Only Redis failures fall back to in-memory — the
                    # endpoint itself must never run twice because a Redis
                    # call raised mid-request.
                    redis_client = None
                if redis_client is not None:
                    return f(*args, **kwargs)

            # In-memory fallback (per-worker, not distributed).
            with _lock:
                # Periodic cleanup of expired entries — prevents unbounded
                # growth of the state dict across process lifetime.
                if now - _last_cleanup > max(window_seconds, 600):
                    _prune_expired(cutoff)
                    _last_cleanup = now

                timestamps = [t for t in state.get(ip, []) if t > cutoff]
                if len(timestamps) >= max_requests:
                    retry_after = int(timestamps[0] - cutoff)
                    return (
                        jsonify(
                            {
                                "error": "Too many requests",
                                "retry_after_seconds": max(retry_after, 1),
                            }
                        ),
                        429,
                    )
                timestamps.append(now)
                state[ip] = timestamps

            return f(*args, **kwargs)

        return decorated

    return decorator
