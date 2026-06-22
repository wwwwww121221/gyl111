from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from typing import Any

from core.redis_client import get_redis
from procurement_agent.schemas import AgentMemoryRecord, AgentSessionSummary


_FALLBACK_MEMORY: dict[str, list[dict[str, Any]]] = defaultdict(list)
_FALLBACK_LONG_TERM_MEMORY: dict[str, list[dict[str, Any]]] = defaultdict(list)
_FALLBACK_SESSION_INDEX: dict[str, list[dict[str, Any]]] = defaultdict(list)
_SESSION_TTL_SECONDS = 60 * 60 * 24
_MAX_MESSAGES = 12
_MAX_LONG_TERM_MEMORIES = 50
_REDIS_RETRY_AFTER = 30
_redis_unavailable_until = 0.0


def new_session_id() -> str:
    return uuid.uuid4().hex


def _key(user_id: int | str, session_id: str) -> str:
    return f"agent:user:{user_id}:session:{session_id}:messages"


def _long_term_key(user_id: int | str) -> str:
    return f"agent:user:{user_id}:long_term_memories"


def _session_index_key(user_id: int | str) -> str:
    return f"agent:user:{user_id}:sessions"


def _get_memory_redis():
    global _redis_unavailable_until
    now = time.time()
    if now < _redis_unavailable_until:
        return None
    try:
        redis = get_redis()
        if not redis:
            _redis_unavailable_until = now + _REDIS_RETRY_AFTER
        return redis
    except Exception:
        _redis_unavailable_until = now + _REDIS_RETRY_AFTER
        return None


def load_messages(user_id: int | str, session_id: str) -> list[dict[str, Any]]:
    key = _key(user_id, session_id)
    try:
        redis = _get_memory_redis()
        if redis:
            rows = redis.lrange(key, 0, -1)
            return [json.loads(row) for row in rows if row]
    except Exception:
        pass
    return list(_FALLBACK_MEMORY.get(key, []))


def list_sessions(user_id: int | str, limit: int = 30) -> list[AgentSessionSummary]:
    rows = _load_session_rows(user_id)
    rows = sorted(rows, key=lambda item: int(item.get("updated_at") or 0), reverse=True)
    return [AgentSessionSummary(**row) for row in rows[:limit]]


def append_message(user_id: int | str, session_id: str, role: str, content: str) -> None:
    key = _key(user_id, session_id)
    now = int(time.time())
    message = {
        "role": role,
        "content": content,
        "created_at": now,
    }
    try:
        redis = _get_memory_redis()
        if redis:
            redis.rpush(key, json.dumps(message, ensure_ascii=False))
            redis.ltrim(key, -_MAX_MESSAGES, -1)
            redis.expire(key, _SESSION_TTL_SECONDS)
            _touch_session_index(user_id, session_id, role, content, now)
            return
    except Exception:
        pass

    rows = _FALLBACK_MEMORY[key]
    rows.append(message)
    del rows[:-_MAX_MESSAGES]
    _touch_session_index(user_id, session_id, role, content, now)


def summarize_recent_messages(messages: list[dict[str, Any]], limit: int = 6) -> str:
    recent = messages[-limit:]
    lines = []
    for item in recent:
        role = item.get("role") or "unknown"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 220:
            content = content[:220] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def list_long_term_memories(user_id: int | str, limit: int = 20) -> list[AgentMemoryRecord]:
    rows = _load_long_term_rows(user_id)
    rows = sorted(rows, key=lambda item: int(item.get("updated_at") or 0), reverse=True)
    return [AgentMemoryRecord(**row) for row in rows[:limit]]


def recall_long_term_memories(user_id: int | str, query: str, limit: int = 3) -> list[AgentMemoryRecord]:
    text = str(query or "").strip()
    if not text:
        return []
    query_terms = _tokenize(text)
    rows = _load_long_term_rows(user_id)
    scored_rows = []
    for row in rows:
        keywords = [str(item).strip().lower() for item in row.get("keywords") or [] if str(item).strip()]
        summary = str(row.get("summary") or "").strip().lower()
        overlap = len(set(query_terms) & set(keywords))
        contains = sum(1 for term in query_terms if term and term in summary)
        score = overlap * 3 + contains
        if score > 0:
            scored_rows.append((score, int(row.get("updated_at") or 0), row))
    scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [AgentMemoryRecord(**row) for _, _, row in scored_rows[:limit]]


def save_long_term_memory(
    user_id: int | str,
    session_id: str,
    summary: str,
    keywords: list[str],
) -> AgentMemoryRecord | None:
    cleaned_summary = str(summary or "").strip()
    cleaned_keywords = _dedupe_keywords(keywords)
    if not cleaned_summary or not cleaned_keywords:
        return None

    rows = _load_long_term_rows(user_id)
    now = int(time.time())
    matched = None
    for row in rows:
        old_keywords = set(_dedupe_keywords(row.get("keywords") or []))
        if set(cleaned_keywords) == old_keywords:
            matched = row
            break

    if matched:
        matched["summary"] = cleaned_summary[:500]
        matched["keywords"] = cleaned_keywords[:12]
        matched["source_session_id"] = session_id
        matched["updated_at"] = now
    else:
        rows.append({
            "id": uuid.uuid4().hex,
            "summary": cleaned_summary[:500],
            "keywords": cleaned_keywords[:12],
            "source_session_id": session_id,
            "created_at": now,
            "updated_at": now,
        })

    rows = sorted(rows, key=lambda item: int(item.get("updated_at") or 0), reverse=True)[:_MAX_LONG_TERM_MEMORIES]
    _save_long_term_rows(user_id, rows)
    return AgentMemoryRecord(**rows[0]) if rows else None


def clear_session_messages(user_id: int | str, session_id: str) -> int:
    key = _key(user_id, session_id)
    count = len(load_messages(user_id, session_id))
    try:
        redis = _get_memory_redis()
        if redis:
            redis.delete(key)
    except Exception:
        pass
    _FALLBACK_MEMORY.pop(key, None)
    _remove_session_index(user_id, session_id)
    return count


def clear_all_session_memories(user_id: int | str) -> int:
    count = 0
    try:
        redis = _get_memory_redis()
        if redis:
            cursor = 0
            pattern = f"agent:user:{user_id}:session:*:messages"
            while True:
                cursor, matched_keys = redis.scan(cursor=cursor, match=pattern, count=100)
                if matched_keys:
                    for key in matched_keys:
                        try:
                            count += redis.llen(key)
                        except Exception:
                            count += 0
                    redis.delete(*matched_keys)
                if cursor == 0:
                    break
    except Exception:
        pass

    prefix = f"agent:user:{user_id}:session:"
    for key in list(_FALLBACK_MEMORY.keys()):
        if key.startswith(prefix):
            count += len(_FALLBACK_MEMORY.get(key, []))
            _FALLBACK_MEMORY.pop(key, None)
    _save_session_rows(user_id, [])
    return count


def clear_long_term_memories(user_id: int | str) -> int:
    key = _long_term_key(user_id)
    rows = _load_long_term_rows(user_id)
    count = len(rows)
    try:
        redis = _get_memory_redis()
        if redis:
            redis.delete(key)
    except Exception:
        pass
    _FALLBACK_LONG_TERM_MEMORY.pop(key, None)
    return count


def _load_long_term_rows(user_id: int | str) -> list[dict[str, Any]]:
    key = _long_term_key(user_id)
    try:
        redis = _get_memory_redis()
        if redis:
            payload = redis.get(key)
            if payload:
                data = json.loads(payload)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return list(_FALLBACK_LONG_TERM_MEMORY.get(key, []))


def _load_session_rows(user_id: int | str) -> list[dict[str, Any]]:
    key = _session_index_key(user_id)
    try:
        redis = _get_memory_redis()
        if redis:
            payload = redis.get(key)
            if payload:
                data = json.loads(payload)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return list(_FALLBACK_SESSION_INDEX.get(key, []))


def _save_long_term_rows(user_id: int | str, rows: list[dict[str, Any]]) -> None:
    key = _long_term_key(user_id)
    payload = json.dumps(rows, ensure_ascii=False)
    try:
        redis = _get_memory_redis()
        if redis:
            redis.set(key, payload)
            return
    except Exception:
        pass
    _FALLBACK_LONG_TERM_MEMORY[key] = list(rows)


def _save_session_rows(user_id: int | str, rows: list[dict[str, Any]]) -> None:
    key = _session_index_key(user_id)
    payload = json.dumps(rows, ensure_ascii=False)
    try:
        redis = _get_memory_redis()
        if redis:
            redis.set(key, payload)
            redis.expire(key, _SESSION_TTL_SECONDS)
            return
    except Exception:
        pass
    _FALLBACK_SESSION_INDEX[key] = list(rows)


def _touch_session_index(user_id: int | str, session_id: str, role: str, content: str, now: int) -> None:
    rows = _load_session_rows(user_id)
    cleaned_content = str(content or "").strip()
    preview = cleaned_content[:120]
    title = preview[:32] or "新对话"

    matched = None
    for row in rows:
        if row.get("session_id") == session_id:
            matched = row
            break

    if matched is None:
        matched = {
            "session_id": session_id,
            "title": title,
            "last_message_preview": preview,
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        rows.append(matched)

    if role == "user" and (not matched.get("title") or matched.get("title") == "新对话"):
        matched["title"] = title
    elif role == "user" and matched.get("message_count", 0) <= 1:
        matched["title"] = title

    matched["last_message_preview"] = preview
    matched["updated_at"] = now
    matched["message_count"] = len(load_messages(user_id, session_id))

    rows = sorted(rows, key=lambda item: int(item.get("updated_at") or 0), reverse=True)[:100]
    _save_session_rows(user_id, rows)


def _remove_session_index(user_id: int | str, session_id: str) -> None:
    rows = [row for row in _load_session_rows(user_id) if row.get("session_id") != session_id]
    _save_session_rows(user_id, rows)


def _tokenize(text: str) -> list[str]:
    normalized = str(text or "").lower()
    for mark in ["，", "。", "、", ",", ".", "?", "？", "；", ";", "：", ":", "\n", "\t", "(", ")", "（", "）"]:
        normalized = normalized.replace(mark, " ")
    parts = [part.strip() for part in normalized.split(" ") if part.strip()]
    return _dedupe_keywords(parts)


def _dedupe_keywords(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        value = str(item or "").strip().lower()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
