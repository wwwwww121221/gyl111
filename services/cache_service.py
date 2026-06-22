import time
from typing import Any

from core.redis_client import cache_get, cache_set


def load_cache_entry(key: str) -> dict[str, Any] | None:
    cached = cache_get(key)
    if not isinstance(cached, dict):
        return None
    if "data" not in cached:
        return None
    return cached


def load_cached_data(key: str) -> Any | None:
    entry = load_cache_entry(key)
    if not entry:
        return None
    return entry.get("data")


def save_cached_data(key: str, data: Any, ttl: int = 0) -> bool:
    payload = {
        "data": data,
        "cached_at": time.time(),
    }
    return cache_set(key, payload, ttl=ttl)


def cache_age_seconds(entry: dict[str, Any] | None) -> int:
    if not isinstance(entry, dict):
        return 10**9
    try:
        cached_at = float(entry.get("cached_at") or 0)
    except (TypeError, ValueError):
        return 10**9
    if cached_at <= 0:
        return 10**9
    return max(0, int(time.time() - cached_at))


def should_refresh_cache(entry: dict[str, Any] | None, soft_ttl: int) -> bool:
    return cache_age_seconds(entry) >= max(0, int(soft_ttl or 0))
