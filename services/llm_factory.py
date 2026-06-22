from abc import ABC, abstractmethod
from typing import Any, List, Optional

import httpx
import logging

from core.config import settings
from schemas import ChatMessage, LLMResponse

logger = logging.getLogger(__name__)


def _extract_http_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error_obj = payload.get("error")
            if isinstance(error_obj, dict):
                code = error_obj.get("code")
                message = error_obj.get("message")
                if code == "Arrearage":
                    return "LLM 服务账号余额不足或欠费，请先在模型平台充值或续费后重试。"
                if message:
                    return str(message)
            if payload.get("message"):
                return str(payload.get("message"))
    except Exception:
        pass
    return (response.text or "未知错误").strip()


def _serialize_message(msg: ChatMessage) -> dict:
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    return msg.dict(exclude_none=True)


class LLMProvider(ABC):
    @abstractmethod
    async def chat_completion(self, messages: List[ChatMessage], **kwargs) -> LLMResponse:
        pass


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat_completion(self, messages: List[ChatMessage], **kwargs) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [_serialize_message(msg) for msg in messages],
            **kwargs,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return LLMResponse(content=content, raw_response=data)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "[LLM HTTP %s] url=%s response=%s",
                    exc.response.status_code,
                    str(exc.request.url),
                    exc.response.text,
                )
                error_message = _extract_http_error_message(exc.response)
                return LLMResponse(
                    content=f"LLM 服务调用失败（HTTP {exc.response.status_code}）：{error_message}",
                    raw_response=exc.response.text,
                )
            except Exception as exc:
                return LLMResponse(content=f"LLM 服务连接异常：{str(exc)}", raw_response=None)


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat_completion(self, messages: List[ChatMessage], **kwargs) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [_serialize_message(msg) for msg in messages],
            "stream": False,
            **kwargs,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                content = data["message"]["content"]
                return LLMResponse(content=content, raw_response=data)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "[LLM HTTP %s] url=%s response=%s",
                    exc.response.status_code,
                    str(exc.request.url),
                    exc.response.text,
                )
                error_message = _extract_http_error_message(exc.response)
                return LLMResponse(
                    content=f"LLM 服务调用失败（HTTP {exc.response.status_code}）：{error_message}",
                    raw_response=exc.response.text,
                )
            except Exception as exc:
                return LLMResponse(content=f"LLM 服务连接异常：{str(exc)}", raw_response=None)


def build_llm_service(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    normalized_provider = str(provider or "").lower()

    if normalized_provider == "ollama":
        return OllamaProvider(
            base_url=base_url or "http://localhost:11434",
            model=model or "llama2",
        )
    if normalized_provider in {"openai", "deepseek"}:
        return OpenAIProvider(
            api_key=api_key or "dummy-key",
            base_url=base_url or "https://api.openai.com/v1",
            model=model or "gpt-3.5-turbo",
        )
    raise ValueError(f"Unsupported LLM provider: {normalized_provider}")


def get_llm_service() -> LLMProvider:
    return build_llm_service(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )


def get_procurement_agent_llm_service() -> LLMProvider:
    return build_llm_service(
        provider=settings.PROCUREMENT_AGENT_LLM_PROVIDER or settings.LLM_PROVIDER,
        api_key=settings.PROCUREMENT_AGENT_LLM_API_KEY or settings.LLM_API_KEY,
        base_url=settings.PROCUREMENT_AGENT_LLM_BASE_URL or settings.LLM_BASE_URL,
        model=settings.PROCUREMENT_AGENT_LLM_MODEL or settings.LLM_MODEL,
    )
