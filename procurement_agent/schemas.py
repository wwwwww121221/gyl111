from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class AgentToolResult(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    data: Any = None


class AgentChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_results: list[AgentToolResult] = Field(default_factory=list)
    memory_count: int = 0


class AgentSessionSummary(BaseModel):
    session_id: str
    title: str
    last_message_preview: str = ""
    message_count: int = 0
    created_at: int
    updated_at: int


class AgentMessageRecord(BaseModel):
    role: str
    content: str
    created_at: int


class AgentMemoryRecord(BaseModel):
    id: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    source_session_id: Optional[str] = None
    created_at: int
    updated_at: int


class AgentMemoryOverview(BaseModel):
    session_id: Optional[str] = None
    short_term_count: int = 0
    long_term_count: int = 0
    long_term_memories: list[AgentMemoryRecord] = Field(default_factory=list)


class AgentMemoryClearRequest(BaseModel):
    session_id: Optional[str] = None
    scope: str = Field(default="current_session", pattern="^(current_session|all_sessions|long_term|all)$")


class AgentMemoryClearResponse(BaseModel):
    scope: str
    cleared_short_term: int = 0
    cleared_long_term: int = 0
