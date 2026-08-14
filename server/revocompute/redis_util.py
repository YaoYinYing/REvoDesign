# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Shared lazy Redis client for distributed rate limiting and CAPTCHA nonces.

Redis is an optional accelerator: when it is unavailable, callers fall back
to per-process in-memory state.  That fallback is documented as per-worker,
not distributed — a CAPTCHA token or rate-limit counter is local to one
gunicorn worker rather than shared across the fleet.  Availability beats
strictness: a Redis outage degrades, never breaks, the endpoints.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

import redis

_LOGGER = logging.getLogger(__name__)

_SOCKET_TIMEOUT = 1  # seconds — fail fast so requests don't pile up on a dead Redis


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis | None:
    """Return a Redis client for ``REDIS_URL``, or ``None`` if unavailable.

    The client (or the ``None`` failure) is cached for the process lifetime
    and the warning is logged once per process.  Call ``get_redis.cache_clear()``
    (e.g. after restarting Redis, or in tests) to re-probe.
    """
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = redis.Redis.from_url(url, socket_timeout=_SOCKET_TIMEOUT, socket_connect_timeout=_SOCKET_TIMEOUT)
    try:
        client.ping()
    except Exception:
        # Never log the URL itself — it may carry the broker password.
        redacted = re.sub(r"://:[^@]*@", "://:***@", url)
        _LOGGER.warning("Redis unavailable at %s — rate limiting and CAPTCHA fall back to per-process state", redacted)
        return None
    return client
