import json
import logging
from typing import Any, Optional

from redis import Redis
from core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
                retry_on_timeout=True,
            )
            _redis_client.ping()
            logger.info("Redis 连接成功: %s", settings.REDIS_URL)
        except Exception as e:
            logger.warning("Redis 连接失败，将使用降级模式: %s", e)
            _redis_client = None
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    """从 Redis 获取缓存数据"""
    r = get_redis()
    if not r:
        return None
    try:
        data = r.get(key)
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.warning("缓存读取失败 key=%s: %s", key, e)
    return None


def cache_set(key: str, value: Any, ttl: int = 0) -> bool:
    """写入 Redis 缓存"""
    r = get_redis()
    if not r:
        return False
    try:
        ttl = ttl or settings.REDIS_CACHE_TTL
        r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        return True
    except Exception as e:
        logger.warning("缓存写入失败 key=%s: %s", key, e)
        return False


def cache_delete(*keys: str) -> bool:
    """删除指定缓存 key"""
    r = get_redis()
    if not r or not keys:
        return False
    try:
        r.delete(*keys)
        return True
    except Exception as e:
        logger.warning("缓存删除失败 keys=%s: %s", keys, e)
        return False


def cache_clear_pattern(pattern: str) -> int:
    """按模式清除缓存（如 supplier:*），返回删除数量"""
    r = get_redis()
    if not r:
        return 0
    try:
        cursor = 0
        count = 0
        while True:
            cursor, matched_keys = r.scan(cursor=cursor, match=pattern, count=100)
            if matched_keys:
                r.delete(*matched_keys)
                count += len(matched_keys)
            if cursor == 0:
                break
        return count
    except Exception as e:
        logger.warning("批量清除缓存失败 pattern=%s: %s", pattern, e)
        return 0
