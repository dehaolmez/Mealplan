"""Basit bellek içi hız sınırlayıcı (tek süreç). Çok süreçli üretimde Redis ile değiştirilmeli."""

import time
from collections import defaultdict, deque
from threading import Lock

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def allow(key: str, limit: int, window_s: int) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def reset() -> None:
    with _lock:
        _hits.clear()
