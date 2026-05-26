"""模拟LLM客户端，用于测试"""

import json
from typing import List
from app.common.llm_client import LLMMessage, LLMResponse


class MockLLMClient:
    """模拟LLM客户端，用于测试"""

    def __init__(self):
        self.call_count = 0
        # TOC 模拟响应
        self._mock_toc_response = {
            "toc": [
                {"title": "第一章 测试章", "level": 0},
                {"title": "1.1 测试节", "level": 1},
                {"title": "1.2 测试节", "level": 1},
                {"title": "第二章 测试章2", "level": 0},
                {"title": "2.1 测试节", "level": 1},
            ]
        }

    @property
    def model(self) -> str:
        return "mock-model"

    def set_assessment_score(self, score: float):
        """兼容接口（已废弃，自评已移除）"""
        pass

    def set_sequential_scores(self, scores: List[float]):
        """兼容接口（已废弃，自评已移除）"""
        pass

    def set_mock_toc_response(self, toc: List[dict]):
        """设置 TOC 模拟响应"""
        self._mock_toc_response = {"toc": toc}

    def _is_toc_request(self, messages: List[LLMMessage]) -> bool:
        """检测是否是 TOC 识别请求"""
        for msg in messages:
            content = msg.content.lower()
            if "目录" in content or "toc" in content or "章节" in content:
                return True
        return False

    def _is_enrich_request(self, messages: List[LLMMessage]) -> bool:
        """检测是否是增量更新请求"""
        for msg in messages:
            content = msg.content
            if "补充" in content or "增量" in content or "enrich" in content.lower():
                return True
        return False

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """模拟聊天 - 始终返回理解响应"""
        self.call_count += 1

        # 检测 TOC 请求
        if self._is_toc_request(messages):
            content = self._mock_toc_response
        elif self._is_enrich_request(messages):
            # 增量更新响应：补充新内容
            content = {
                "summary": "补充后的摘要，增加了更多细节和示例说明。",
                "key_points": [
                    "补充要点1：实际应用案例",
                    "补充要点2：与其他概念的关联",
                ],
                "concepts": [
                    {
                        "name": "补充概念C",
                        "definition": "概念C的定义（补充）",
                        "examples": ["补充示例"],
                        "related_concepts": ["测试概念A"],
                    },
                ],
                "difficulty_level": 3,
                "importance_score": 0.8,
                "prerequisites": [],
            }
        else:
            content = {
                "summary": "这是一个测试摘要，包含了核心概念的解释和应用。",
                "key_points": [
                    "要点1：基本概念",
                    "要点2：核心原理",
                    "要点3：实际应用",
                ],
                "concepts": [
                    {
                        "name": "测试概念A",
                        "definition": "概念A的定义",
                        "examples": ["示例1"],
                        "related_concepts": ["概念B"],
                    },
                    {
                        "name": "测试概念B",
                        "definition": "概念B的定义",
                        "examples": ["示例2"],
                        "related_concepts": ["概念A"],
                    },
                ],
                "difficulty_level": 3,
                "importance_score": 0.7,
                "prerequisites": ["前置知识1"],
            }

        return LLMResponse(
            content=json.dumps(content),
            model="mock-model",
            usage={
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
            },
        )

    async def chat_json(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """JSON模式聊天 - 调用chat并解析JSON"""
        response = await self.chat(messages, temperature, max_tokens)
        return json.loads(response.content)
