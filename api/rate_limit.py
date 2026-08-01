"""
Simple in-memory rate limiter for the Aidr pilot.

Fine for a single uvicorn worker. For multi-instance deploy, swap to Redis later.
Configure via env:
  AIDR_RATE_LIMIT_PER_MIN=20      # per key (phone hash or IP)
  AIDR_RATE_LIMIT_SEARCH_PER_MIN=30
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional, Tuple


_lock = Lock()
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _limit(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def per_minute_limit(name: str, default: int) -> int:
    return _limit(name, default)


def allow(key: str, *, per_minute: Optional[int] = None, scope: str = "default") -> Tuple[bool, int]:
    """
    Return (allowed, retry_after_seconds).
    key should already be hashed / non-PII when possible.
    """
    limit = per_minute if per_minute is not None else _limit("AIDR_RATE_LIMIT_PER_MIN", 20)
    now = time.time()
    window = 60.0
    bucket_key = f"{scope}:{key}"

    with _lock:
        q = _buckets[bucket_key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, int(window - (now - q[0])) + 1)
            return False, retry
        q.append(now)
        return True, 0
