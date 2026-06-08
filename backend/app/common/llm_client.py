"""LLM客户端抽象和OpenAI实现"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Protocol
from pydantic import BaseModel
import httpx

from app.common.errors import ServiceError, ErrorCode

logger = logging.getLogger(__name__)

# 全局信号量，控制并发 LLM 请求数
_semaphore: asyncio.Semaphore | None = None

# 优雅关闭事件：设置后拒绝新的 LLM 请求，允许在途请求完成
_shutdown_event: asyncio.Event = asyncio.Event()

# 当前在途请求数
_inflight_count: int = 0
_inflight_lock: asyncio.Lock = asyncio.Lock()


def init_semaphore(max_concurrent: int) -> None:
    """初始化或更新并发信号量"""
    global _semaphore
    _semaphore = asyncio.Semaphore(max_concurrent)
    logger.info(f"LLM 并发信号量已设置为 {max_concurrent}")


def request_shutdown() -> None:
    """通知 LLM 客户端开始优雅关闭"""
    _shutdown_event.set()
    logger.info("LLM 客户端：已发出关闭信号，等待在途请求完成...")


async def wait_inflight(timeout: float = 60.0) -> None:
    """等待所有在途 LLM 请求完成"""
    import time
    deadline = time.monotonic() + timeout
    while True:
        async with _inflight_lock:
            count = _inflight_count
        if count <= 0:
            break
        if time.monotonic() >= deadline:
            logger.warning(f"LLM 客户端：{timeout}秒后仍有 {count} 个请求未完成，强制关闭")
            return
        await asyncio.sleep(0.5)
    logger.info("LLM 客户端：所有在途请求已完成")


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: Dict[str, Any]


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMClient(Protocol):
    async def chat(self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse: ...
    async def chat_json(self, messages: List[LLMMessage], temperature: float = 0.3, max_tokens: int = 4096) -> dict: ...
    async def close(self) -> None: ...


class OpenAIClient:
    """使用httpx异步调用OpenAI API的客户端（实现 LLMClient 协议）"""

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=300.0)

    async def _call_api(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int,
                        response_format: Dict[str, str] | None = None) -> Dict[str, Any]:
        """调用OpenAI Chat Completions API（受并发信号量控制）"""
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

        # 使用信号量控制并发
        sem = _semaphore
        max_retries = 3

        async def _do_request():
            global _inflight_count
            # 拒绝新请求：服务器正在关闭
            if _shutdown_event.is_set():
                raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "服务器正在关闭，请稍后重试")

            async with _inflight_lock:
                _inflight_count += 1
            try:
                last_exc = None
                for attempt in range(max_retries):
                    if _shutdown_event.is_set():
                        raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "服务器正在关闭，请稍后重试")
                    try:
                        resp = await self._client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                        resp.raise_for_status()
                        return resp.json()
                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        if status == 429 or status >= 500:
                            # 可重试的 HTTP 错误：429 限流 / 5xx 服务端错误
                            last_exc = e
                            if attempt < max_retries - 1:
                                wait = 2 ** attempt
                                logger.warning(f"LLM API HTTP {status} (第{attempt+1}次): {wait}秒后重试...")
                                await asyncio.sleep(wait)
                                continue
                        logger.error(f"LLM API HTTP错误: {status} {e.response.text[:200]}")
                        raise ServiceError(
                            ErrorCode.EXTERNAL_API_ERROR,
                            f"LLM API 返回 {status}",
                            {"status_code": status, "body": e.response.text[:500]},
                        )
                    except httpx.TimeoutException as e:
                        last_exc = e
                        if attempt < max_retries - 1:
                            wait = 2 ** attempt
                            logger.warning(f"LLM API 超时 (第{attempt+1}次): {wait}秒后重试...")
                            await asyncio.sleep(wait)
                            continue
                        logger.error("LLM API 超时 (重试耗尽)")
                        raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM API 超时，请稍后重试")
                    except httpx.RequestError as e:
                        last_exc = e
                        if attempt < max_retries - 1:
                            wait = 2 ** attempt
                            logger.warning(f"LLM API 瞬时网络错误 (第{attempt+1}次): {e}，{wait}秒后重试...")
                            await asyncio.sleep(wait)
                        else:
                            logger.error(f"LLM API 请求失败 (重试{max_retries}次后): {e}")
                            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, f"LLM API 请求失败: {e}")
                # 所有重试耗尽
                raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, f"LLM API 请求失败 (重试{max_retries}次后): {last_exc}")
            finally:
                async with _inflight_lock:
                    _inflight_count -= 1

        if sem is not None:
            async with sem:
                return await _do_request()
        return await _do_request()

    async def chat(self, messages: List[LLMMessage], temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse:
        """普通聊天接口"""
        raw_messages = [{"role": m.role, "content": m.content} for m in messages]
        data = await self._call_api(raw_messages, temperature, max_tokens)
        if not data.get("choices"):
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM API 返回了空的 choices")
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model=data["model"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    async def chat_json(self, messages: List[LLMMessage], temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """JSON模式聊天接口，解析失败时附带修正指令重试一次"""
        raw_messages = [{"role": m.role, "content": m.content} for m in messages]

        # 第一次尝试：使用JSON mode
        data = await self._call_api(raw_messages, temperature, max_tokens, response_format={"type": "json_object"})
        if not data.get("choices"):
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM API 返回了空的 choices")
        content = data["choices"][0]["message"]["content"]

        try:
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM 返回的JSON不是字典类型")
            return result
        except json.JSONDecodeError:
            pass

        # 重试：附带格式修正指令
        fix_messages = raw_messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "你的回复不是有效JSON。请重新输出，只返回纯JSON，不要包含任何其他文本或markdown标记。"},
        ]
        data = await self._call_api(fix_messages, temperature, max_tokens, response_format={"type": "json_object"})
        if not data.get("choices"):
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM API 返回了空的 choices")
        content = data["choices"][0]["message"]["content"]
        try:
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM 返回的JSON不是字典类型")
            return result
        except json.JSONDecodeError:
            logger.error(f"LLM返回JSON解析失败（重试后）: {content[:200]}")
            raise ServiceError(
                ErrorCode.EXTERNAL_API_ERROR,
                "LLM 返回了无效的JSON格式，请重试",
            )

    async def close(self):
        await self._client.aclose()
