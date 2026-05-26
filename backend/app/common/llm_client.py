"""LLM客户端抽象和OpenAI实现"""
import json
import logging
from typing import List, Dict, Any, Protocol
from pydantic import BaseModel
import httpx

from app.common.errors import ServiceError, ErrorCode

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: Dict[str, int]


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMClient(Protocol):
    async def chat(self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse: ...
    async def chat_json(self, messages: List[LLMMessage], temperature: float = 0.3, max_tokens: int = 4096) -> dict: ...


class OpenAIClient:
    """使用httpx异步调用OpenAI API的客户端"""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    async def _call_api(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int,
                        response_format: Dict[str, str] | None = None) -> Dict[str, Any]:
        """调用OpenAI Chat Completions API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        try:
            resp = await self._client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API HTTP错误: {e.response.status_code} {e.response.text[:200]}")
            raise ServiceError(
                ErrorCode.EXTERNAL_API_ERROR,
                f"LLM API 返回 {e.response.status_code}",
                {"status_code": e.response.status_code, "body": e.response.text[:500]},
            )
        except httpx.TimeoutException:
            logger.error("LLM API 超时")
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM API 超时，请稍后重试")
        except httpx.RequestError as e:
            logger.error(f"LLM API 请求失败: {e}")
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, f"LLM API 请求失败: {e}")

    async def chat(self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse:
        """普通聊天接口"""
        raw_messages = [{"role": m.role, "content": m.content} for m in messages]
        data = await self._call_api(raw_messages, temperature, max_tokens)
        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data["model"],
            usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        )

    async def chat_json(self, messages: List[LLMMessage], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """JSON模式聊天接口，解析失败时附带修正指令重试一次"""
        raw_messages = [{"role": m.role, "content": m.content} for m in messages]

        # 第一次尝试：使用JSON mode
        data = await self._call_api(raw_messages, temperature, max_tokens, response_format={"type": "json_object"})
        content = data["choices"][0]["message"]["content"]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 重试：附带格式修正指令
        fix_messages = raw_messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "你的回复不是有效JSON。请重新输出，只返回纯JSON，不要包含任何其他文本或markdown标记。"},
        ]
        data = await self._call_api(fix_messages, temperature, max_tokens, response_format={"type": "json_object"})
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"LLM返回JSON解析失败（重试后）: {content[:200]}")
            raise ServiceError(
                ErrorCode.EXTERNAL_API_ERROR,
                "LLM 返回了无效的JSON格式，请重试",
            )

    async def close(self):
        await self._client.aclose()
