# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Simple in-memory rate limiter for sensitive endpoints.

Per-worker, not distributed — raises the bar against brute-force but
doesn't provide hard guarantees across multiple gunicorn workers.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import jsonify, request


def rate_limit(max_requests: int, window_seconds: int):
    """Decorator: allow at most *max_requests* per *window_seconds* per IP.

    Usage::

        @app.route("/login", methods=["POST"])
        @rate_limit(max_requests=5, window_seconds=60)
        def login():
            ...
    """
    state: dict[str, list[float]] = {}
    _lock = threading.Lock()
    _last_cleanup: float = 0.0

    def _prune_expired(now: float, cutoff: float) -> None:
        """Drop per-IP entries whose most recent timestamp is expired."""
        empty = [ip for ip, ts in state.items() if not ts or ts[-1] <= cutoff]
        for ip in empty:
            del state[ip]

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            nonlocal _last_cleanup
            ip = request.remote_addr or "unknown"
            now = time.time()
            cutoff = now - window_seconds

            with _lock:
                # Periodic cleanup of expired entries — prevents unbounded
                # growth of the state dict across process lifetime.
                if now - _last_cleanup > max(window_seconds, 600):
                    _prune_expired(now, cutoff)
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
