from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from models import User, get_db
from procurement_agent.memory import (
    clear_all_session_memories,
    clear_long_term_memories,
    clear_session_messages,
    list_sessions,
    load_messages,
    new_session_id,
)
from procurement_agent.runner import ProcurementAgentRunner
from procurement_agent.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentMemoryClearRequest,
    AgentMemoryClearResponse,
    AgentMessageRecord,
    AgentMemoryOverview,
    AgentSessionSummary,
)
from routers.auth import get_current_user_auth

router = APIRouter()


def _require_procurement_roles(current_user: User) -> None:
    if current_user.role not in ["admin", "buyer", "buyer_manager"]:
        raise HTTPException(status_code=403, detail="Only procurement users can use the procurement assistant")


@router.get("/status")
def get_agent_status(current_user: User = Depends(get_current_user_auth)) -> dict[str, Any]:
    _require_procurement_roles(current_user)
    return {
        "enabled": True,
        "provider": settings.PROCUREMENT_AGENT_LLM_PROVIDER or settings.LLM_PROVIDER,
        "model": settings.PROCUREMENT_AGENT_LLM_MODEL or settings.LLM_MODEL,
        "has_api_key": bool(settings.PROCUREMENT_AGENT_LLM_API_KEY or settings.LLM_API_KEY),
    }


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    payload: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> AgentChatResponse:
    _require_procurement_roles(current_user)
    runner = ProcurementAgentRunner(db, current_user)
    return await runner.chat(payload.message, payload.session_id, payload.context or {})


@router.post("/sessions")
def create_agent_session(current_user: User = Depends(get_current_user_auth)) -> dict[str, str]:
    _require_procurement_roles(current_user)
    return {"session_id": new_session_id()}


@router.get("/sessions", response_model=list[AgentSessionSummary])
def get_agent_sessions(current_user: User = Depends(get_current_user_auth)) -> list[AgentSessionSummary]:
    _require_procurement_roles(current_user)
    return list_sessions(current_user.id)


@router.get("/sessions/{session_id}/messages", response_model=list[AgentMessageRecord])
def get_agent_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user_auth),
) -> list[AgentMessageRecord]:
    _require_procurement_roles(current_user)
    rows = load_messages(current_user.id, session_id)
    return [AgentMessageRecord(**row) for row in rows]


@router.get("/memory", response_model=AgentMemoryOverview)
def get_agent_memory(
    session_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_auth),
) -> AgentMemoryOverview:
    _require_procurement_roles(current_user)
    runner = ProcurementAgentRunner(db, current_user)
    return AgentMemoryOverview(**runner.get_memory_overview(session_id))


@router.post("/memory/clear", response_model=AgentMemoryClearResponse)
def clear_agent_memory(
    payload: AgentMemoryClearRequest,
    current_user: User = Depends(get_current_user_auth),
) -> AgentMemoryClearResponse:
    _require_procurement_roles(current_user)

    cleared_short_term = 0
    cleared_long_term = 0

    if payload.scope == "current_session":
        if not payload.session_id:
            raise HTTPException(status_code=400, detail="session_id is required when clearing the current session")
        cleared_short_term = clear_session_messages(current_user.id, payload.session_id)
    elif payload.scope == "all_sessions":
        cleared_short_term = clear_all_session_memories(current_user.id)
    elif payload.scope == "long_term":
        cleared_long_term = clear_long_term_memories(current_user.id)
    elif payload.scope == "all":
        cleared_short_term = clear_all_session_memories(current_user.id)
        cleared_long_term = clear_long_term_memories(current_user.id)

    return AgentMemoryClearResponse(
        scope=payload.scope,
        cleared_short_term=cleared_short_term,
        cleared_long_term=cleared_long_term,
    )
