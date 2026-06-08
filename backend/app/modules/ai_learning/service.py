"""AI学习服务 - 核心学习引擎"""

import asyncio
import json
import logging
import time
from typing import List, Optional, Callable
from datetime import datetime

from sqlalchemy import select

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.common.json_utils import parse_llm_json
from app.db.models import KnowledgeUnitModel, MasteryRecordModel
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter
from app.modules.ai_learning.schemas import (
    LearnedUnit,
    KeyPoint,
    Concept,
    LearningContext,
    LearningProgress,
    BookLearningResult,
    BookOverview,
    ChapterOverview,
    LearningStatus,
)
from app.modules.ai_learning.prompts import build_understand_prompt, build_merge_prompt, build_enrich_prompt, FOCUS_DIRECTIONS
from app.modules.ai_learning.token_optimizer import TokenOptimizer

logger = logging.getLogger(__name__)


class AILearningService:
    """AI学习服务"""

    def __init__(
        self,
        llm_client: LLMClient,
        db_session=None,
        token_budget: Optional[int] = None,
    ):
        self.llm = llm_client
        self.db = db_session
        self.token_budget = token_budget
        self.optimizer = TokenOptimizer()
        self._total_tokens_used = 0
        self._last_large_unit_tokens = 0  # 大单元内部 LLM 调用的 token 累计
        self._on_unit_learned = None  # 学完单元后的回调（用于图谱增量更新）

    # 超过此字符数视为"大单元"，启用递归摘要
    LARGE_UNIT_THRESHOLD = 5000

    # 大单元分块时每块的最大字符数（与阈值解耦）
    MAX_CHUNK_CHAR_SIZE = 7000

    @staticmethod
    def _try_parse_json(json_str: str) -> Optional[dict]:
        """尝试解析 JSON，失败时尝试修复常见错误（如尾部逗号）"""
        import re
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"[_try_parse_json] 直接解析失败: {e}, 内容长度={len(json_str)}")
            pass
        # 移除可能的尾部逗号
        fixed = re.sub(r',\s*}', '}', json_str)
        fixed = re.sub(r',\s*]', ']', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.debug(f"[_try_parse_json] 修复尾部逗号后仍失败: {e}")
            return None

    @staticmethod
    def _try_parse_truncated_json(text: str) -> Optional[dict]:
        """尝试修复截断的 JSON（LLM 响应被 token 限制切断的情况）"""
        import re
        logger.debug(f"[_try_parse_truncated_json] 输入长度={len(text)}, 尾部50字符: {repr(text[-50:])}")

        # 策略1: 找到最后一个完整的 } 或 ]
        last_brace = max(text.rfind('}'), text.rfind(']'))
        if last_brace > 0:
            text = text[:last_brace + 1]

        # 移除尾部逗号
        text = text.rstrip().rstrip(',')

        # 策略2: 找到最后一个完整的键值对（以 } 或 ] 结尾的行）
        # 从后往前扫描，找到最后一个完整的值
        lines = text.split('\n')
        # 从后往前找，找到第一个以 } 或 ] 或 ", 结尾的行
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.endswith('}') or stripped.endswith(']') or stripped.endswith('",') or stripped.endswith('"'):
                # 检查这一行是否是完整的（不包含未闭合的引号）
                quote_count = stripped.count('"') - stripped.count('\\"')
                if quote_count % 2 == 0:  # 引号数量是偶数，说明完整
                    text = '\n'.join(lines[:i + 1])
                    break

        # 移除尾部逗号
        text = text.rstrip().rstrip(',')

        # 补全缺失的括号
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        text += ']' * max(0, open_brackets)
        text += '}' * max(0, open_braces)

        # 尝试解析
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                logger.debug(f"[_try_parse_truncated_json] 修复成功, keys={list(result.keys())}")
                return result
        except json.JSONDecodeError as e:
            logger.warning(f"[_try_parse_truncated_json] 第一次修复失败: {e}")

        # 策略3: 更激进的修复 - 尝试只提取 summary、explanation 和 key_points
        try:
            # 用正则提取 summary
            summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            summary = summary_match.group(1) if summary_match else ""

            # 用正则提取 explanation
            explanation_match = re.search(r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            explanation = explanation_match.group(1) if explanation_match else ""

            # 用正则提取 key_points（使用非贪婪匹配，支持嵌套括号）
            kp_match = re.search(r'"key_points"\s*:\s*\[(\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*)\]', text, re.DOTALL)
            key_points = []
            if kp_match:
                kp_text = kp_match.group(1)
                # 尝试解析为 JSON 数组
                try:
                    parsed_kps = json.loads(f"[{kp_text}]")
                    key_points = [
                        {"title": kp.get("title", ""), "explanation": kp.get("explanation", ""),
                         "examples": kp.get("examples", []) if isinstance(kp.get("examples"), list) else []}
                        for kp in parsed_kps if isinstance(kp, dict) and kp.get("title")
                    ]
                except (json.JSONDecodeError, AttributeError):
                    # 回退：逐个提取 title/explanation 对
                    kp_objects = re.findall(
                        r'\{\s*"title"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"',
                        kp_text,
                    )
                    key_points = [{"title": t, "explanation": e, "examples": []} for t, e in kp_objects]

                    # 如果仍然没有提取到，尝试从扁平的 "title"/"explanation" 键值对重建
                    if not key_points:
                        titles = re.findall(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', kp_text)
                        explanations = re.findall(r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', kp_text)
                        for idx, title in enumerate(titles):
                            exp = explanations[idx] if idx < len(explanations) else ""
                            key_points.append({"title": title, "explanation": exp, "examples": []})

            # 用正则提取 concepts（尝试提取 name/definition 对）
            concepts = []
            concepts_match = re.search(r'"concepts"\s*:\s*\[(\s*\{.*?\}\s*(?:,\s*\{.*?\}\s*)*)\]', text, re.DOTALL)
            if concepts_match:
                c_text = concepts_match.group(1)
                try:
                    parsed_cs = json.loads(f"[{c_text}]")
                    concepts = [
                        {"name": c.get("name", ""), "definition": c.get("definition", ""),
                         "examples": c.get("examples", []) if isinstance(c.get("examples"), list) else [],
                         "related_concepts": c.get("related_concepts", []) if isinstance(c.get("related_concepts"), list) else []}
                        for c in parsed_cs if isinstance(c, dict) and c.get("name")
                    ]
                except (json.JSONDecodeError, AttributeError):
                    names = re.findall(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"', c_text)
                    defs = re.findall(r'"definition"\s*:\s*"((?:[^"\\]|\\.)*)"', c_text)
                    for idx, name in enumerate(names):
                        d = defs[idx] if idx < len(defs) else ""
                        concepts.append({"name": name, "definition": d, "examples": [], "related_concepts": []})

            if summary:
                result = {
                    "summary": summary,
                    "explanation": explanation,
                    "key_points": key_points,
                    "concepts": concepts,
                    "difficulty_level": 3,
                    "importance_score": 0.5,
                    "prerequisites": []
                }
                logger.debug(f"[_try_parse_truncated_json] 正则提取成功, summary长度={len(summary)}, "
                             f"key_points={len(key_points)}, concepts={len(concepts)}")
                return result
        except Exception as ex:
            logger.warning(f"[_try_parse_truncated_json] 正则提取失败: {ex}")

        return None

    def _extract_json(self, text: str) -> dict:
        """从 LLM 响应中提取 JSON（支持 markdown 代码块格式）"""
        import re

        # 如果已经是 dict，直接返回
        if isinstance(text, dict):
            return text

        logger.debug(f"[_extract_json] 响应长度={len(text)}, 前100字符: {text[:100]}")

        try:
            return parse_llm_json(text)
        except ValueError:
            pass

        match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?```|$)', text, re.DOTALL)
        if match:
            extracted = match.group(1)
            logger.debug(f"[_extract_json] 正则提取内容长度={len(extracted)}, 前100字符: {extracted[:100]}")
            result = self._try_parse_truncated_json(extracted)
            if result is not None:
                logger.debug("[_extract_json] 正则提取后截断修复成功")
                return result

        start = text.find('{')
        if start != -1:
            truncated = text[start:]
            logger.debug(f"[_extract_json] 尝试截断修复, 截断内容长度={len(truncated)}")
            result = self._try_parse_truncated_json(truncated)
            if result is not None:
                logger.debug("[_extract_json] 截断修复成功")
                return result

        logger.error(f"[_extract_json] 所有方法均失败, 响应内容: {text[:500]}")
        raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}")

    @staticmethod
    def _normalize_key_points(raw: list) -> list[dict]:
        """将混合格式的 key_points 统一为 dict 列表（兼容旧字符串格式）"""
        result = []
        for kp in raw:
            if isinstance(kp, dict):
                result.append(kp)
            elif isinstance(kp, str):
                result.append({"title": kp, "explanation": "", "examples": []})
        return result

    @staticmethod
    def _validate_parsed_result(data: dict) -> bool:
        """校验解析结果的质量，检测畸形数据。

        返回 True 表示结果可用，False 表示结果质量不合格（可能是截断/解析错误导致）。
        """
        if not isinstance(data, dict):
            return False

        # 必须有 summary
        summary = data.get("summary", "")
        if not summary or len(summary) < 20:
            logger.warning(f"[_validate] summary 过短或缺失: {len(summary)} 字符")
            return False

        # key_points 必须是列表
        kps = data.get("key_points", [])
        if not isinstance(kps, list):
            logger.warning(f"[_validate] key_points 不是列表: {type(kps)}")
            return False

        # key_points 中至少有一半应该是 dict 且含 title 字段
        if kps:
            dict_count = sum(1 for kp in kps if isinstance(kp, dict) and kp.get("title"))
            if dict_count < len(kps) * 0.5:
                logger.warning(f"[_validate] key_points 格式异常: {len(kps)} 个中仅 {dict_count} 个有 title")
                return False

        # concepts 如果存在，应该是列表
        concepts = data.get("concepts", [])
        if concepts and not isinstance(concepts, list):
            logger.warning(f"[_validate] concepts 不是列表: {type(concepts)}")
            return False

        # concepts 中至少有一半应该是 dict 且含 name 字段
        if concepts:
            dict_count = sum(1 for c in concepts if isinstance(c, dict) and c.get("name"))
            if dict_count < len(concepts) * 0.5:
                logger.warning(f"[_validate] concepts 格式异常: {len(concepts)} 个中仅 {dict_count} 个有 name")
                return False

        return True

    async def learn_unit(
        self, unit: KnowledgeUnit, context: LearningContext,
        on_progress: Optional[Callable] = None,
    ) -> LearnedUnit:
        """
        学习单个知识单元。

        流程：
        1. 判断单元大小：
           - 小单元（<=2000字）→ 直接调 LLM 分析
           - 大单元（>2000字）→ 递归摘要（Map-Reduce）
             a. 按段落切成子块（每块 <=2000字）
             b. 并发调 LLM 分析各子块（Map）
             c. 调 LLM 整合所有子块结果（Reduce）
        2. 直接返回 LearnedUnit（self_assessment=None）
        """
        if on_progress:
            on_progress(-1, 0, f"正在分析「{unit.title}」...")
        if len(unit.content) > self.LARGE_UNIT_THRESHOLD:
            # ── 大单元：递归摘要 ──
            context_info = self._build_context_info(context, 0)
            self._last_large_unit_tokens = 0
            understand_result = await self._learn_large_unit(
                unit, context_info, on_progress
            )
            token_cost = self._last_large_unit_tokens
        else:
            # ── 小单元：单次 LLM 理解调用 ──
            context_info = self._build_context_info(context, 0)
            prompt = build_understand_prompt(
                content=unit.content,
                context_info=context_info,
            )
            response = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=16384,
            )
            token_cost = (response.usage or {}).get("total_tokens", 0)
            understand_result = self._extract_json(response.content)

            # 质量校验：失败则重试一次
            if not self._validate_parsed_result(understand_result):
                logger.warning(f"单元「{unit.title}」首次解析结果质量不合格，重试...")
                response = await self.llm.chat(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.2,
                    max_tokens=16384,
                )
                token_cost += (response.usage or {}).get("total_tokens", 0)
                understand_result = self._extract_json(response.content)

        concepts = [Concept(**c) for c in understand_result.get("concepts", [])]
        raw_kps = self._normalize_key_points(understand_result.get("key_points", []))
        key_points = [KeyPoint(**kp) for kp in raw_kps]

        learned = LearnedUnit(
            unit_id=unit.id,
            book_id=unit.book_id,
            summary=understand_result.get("summary", ""),
            explanation=understand_result.get("explanation", ""),
            key_points=key_points,
            concepts=concepts,
            difficulty_level=understand_result.get("difficulty_level", 3),
            importance_score=understand_result.get("importance_score", 0.5),
            prerequisites=understand_result.get("prerequisites", []),
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=token_cost,
        )

        await self._persist_learned_unit(learned)
        return learned

    # 每次 Map-Reduce 处理的最大子块数
    MAX_CHUNKS_PER_ROUND = 10

    def _split_content(self, content: str) -> list[str]:
        """将内容按段落切分为子块（每块 <=MAX_CHUNK_CHAR_SIZE）"""
        import re
        paragraphs = re.split(r'\n\n+', content)
        chunks: list[str] = []
        buf = ""
        for para in paragraphs:
            if len(buf) + len(para) + 2 <= self.MAX_CHUNK_CHAR_SIZE:
                buf += ("\n\n" if buf else "") + para
            else:
                if buf:
                    chunks.append(buf)
                # 单段就超长 → 硬切
                while len(para) > self.MAX_CHUNK_CHAR_SIZE:
                    chunks.append(para[:self.MAX_CHUNK_CHAR_SIZE])
                    para = para[self.MAX_CHUNK_CHAR_SIZE:]
                buf = para
        if buf:
            chunks.append(buf)
        return chunks

    async def _learn_large_unit(
        self, unit: KnowledgeUnit, context_info: str,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """递归摘要：大单元先分块分析，再整合。
        对于超长内容（块数 > MAX_CHUNKS_PER_ROUND），采用多级 Map-Reduce：
        先分批处理，每批整合为中间摘要，最后再整合所有中间摘要。
        """
        chunks = self._split_content(unit.content)

        # 分批处理，每批最多 MAX_CHUNKS_PER_ROUND 块
        batch_results: list[dict] = []
        for batch_start in range(0, len(chunks), self.MAX_CHUNKS_PER_ROUND):
            batch = chunks[batch_start:batch_start + self.MAX_CHUNKS_PER_ROUND]
            logger.info(
                f"单元「{unit.title}」处理第 {batch_start // self.MAX_CHUNKS_PER_ROUND + 1} "
                f"批（{batch_start + 1}-{batch_start + len(batch)}/{len(chunks)} 块）"
            )

            # Map：并发分析本批子块
            if on_progress:
                on_progress(batch_start / len(chunks), 0, f"分析「{unit.title}」第 {batch_start + 1}-{batch_start + len(batch)}/{len(chunks)} 块...")

            async def _analyze_chunk(chunk: str) -> dict:
                prompt = build_understand_prompt(
                    content=chunk,
                    context_info=f"（这是大单元「{unit.title}」的一部分，请分析这段内容）",
                )
                resp = await self.llm.chat(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.3,
                    max_tokens=16384,
                )
                self._last_large_unit_tokens += (resp.usage or {}).get("total_tokens", 0)
                return self._extract_json(resp.content)

            sub_results = await asyncio.gather(*[_analyze_chunk(c) for c in batch], return_exceptions=True)
            valid_results = []
            for r in sub_results:
                if isinstance(r, Exception):
                    logger.error(f"子块分析失败: {r}")
                else:
                    valid_results.append(r)
            if not valid_results:
                raise ServiceError(ErrorCode.PROCESSING_ERROR, "所有子块分析均失败")
            sub_results = valid_results

            # 只有一块 → 直接用
            if len(sub_results) == 1:
                batch_results.append(sub_results[0])
                continue

            # Reduce：整合本批子块
            if on_progress:
                on_progress((batch_start + len(batch)) / len(chunks), 0, f"整合「{unit.title}」第 {batch_start // self.MAX_CHUNKS_PER_ROUND + 1} 批结果...")
            try:
                merge_prompt = build_merge_prompt(
                    unit_title=unit.title,
                    sub_results=sub_results,
                    context_info=context_info,
                )
                merge_resp = await self.llm.chat(
                    messages=[LLMMessage(role="user", content=merge_prompt)],
                    temperature=0.3,
                    max_tokens=16384,
                )
                self._last_large_unit_tokens += (merge_resp.usage or {}).get("total_tokens", 0)
                merge_result = self._extract_json(merge_resp.content)
                # 质量校验：失败则重试一次
                if not self._validate_parsed_result(merge_result):
                    logger.warning(f"Reduce 整合结果质量不合格，重试...")
                    merge_resp = await self.llm.chat(
                        messages=[LLMMessage(role="user", content=merge_prompt)],
                        temperature=0.2,
                        max_tokens=16384,
                    )
                    self._last_large_unit_tokens += (merge_resp.usage or {}).get("total_tokens", 0)
                    merge_result = self._extract_json(merge_resp.content)
                batch_results.append(merge_result)
            except Exception as merge_err:
                # Reduce 失败时降级：取第一个子块结果作为本批代表
                logger.warning(f"Reduce 整合失败，降级使用子块结果: {merge_err}")
                batch_results.append(sub_results[0])

        # 只有一批 → 直接返回
        if len(batch_results) == 1:
            return batch_results[0]

        # 多批 → 最终整合
        logger.info(f"单元「{unit.title}」最终整合 {len(batch_results)} 个批次结果")
        if on_progress:
            on_progress(-1, 0, f"最终整合「{unit.title}」的 {len(batch_results)} 个批次...")
        try:
            final_prompt = build_merge_prompt(
                unit_title=unit.title,
                sub_results=batch_results,
                context_info=context_info,
            )
            final_resp = await self.llm.chat(
                messages=[LLMMessage(role="user", content=final_prompt)],
                temperature=0.3,
                max_tokens=16384,
            )
            self._last_large_unit_tokens += (final_resp.usage or {}).get("total_tokens", 0)
            final_result = self._extract_json(final_resp.content)
            # 质量校验：失败则重试一次
            if not self._validate_parsed_result(final_result):
                logger.warning(f"最终整合结果质量不合格，重试...")
                final_resp = await self.llm.chat(
                    messages=[LLMMessage(role="user", content=final_prompt)],
                    temperature=0.2,
                    max_tokens=16384,
                )
                self._last_large_unit_tokens += (final_resp.usage or {}).get("total_tokens", 0)
                final_result = self._extract_json(final_resp.content)
            return final_result
        except Exception as merge_err:
            # 最终整合失败时降级：取第一个批次结果
            logger.warning(f"最终整合失败，降级使用首个批次结果: {merge_err}")
            return batch_results[0]

    async def _persist_learned_unit(self, learned: LearnedUnit) -> None:
        """将 AI 学习结果写回 knowledge_units 表"""
        if self.db is None:
            return

        result = await self.db.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == learned.unit_id)
        )
        db_unit = result.scalar_one_or_none()
        if db_unit is None:
            return

        db_unit.summary = learned.summary
        db_unit.explanation = learned.explanation
        db_unit.key_points = json.dumps(
            [{"title": kp.title, "explanation": kp.explanation, "examples": kp.examples}
             for kp in learned.key_points],
            ensure_ascii=False,
        )
        # 存完整 Concept 对象（含 definition/examples/related_concepts）
        db_unit.concepts = json.dumps(
            [{"name": c.name, "definition": c.definition,
              "examples": c.examples, "related_concepts": c.related_concepts}
             for c in learned.concepts],
            ensure_ascii=False,
        )
        # prerequisites 优先存 unit_id，其次存概念名
        db_unit.prerequisites = json.dumps(learned.prerequisites, ensure_ascii=False)
        db_unit.difficulty_level = learned.difficulty_level
        db_unit.importance_score = learned.importance_score

        # 创建/更新掌握度记录（标记为已学习）
        from uuid import uuid4
        from datetime import timezone
        now = datetime.now(timezone.utc)
        existing = await self.db.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == "anonymous",
                MasteryRecordModel.knowledge_unit_id == learned.unit_id,
            )
        )
        mastery = existing.scalar_one_or_none()
        if mastery:
            mastery.last_reviewed_at = now
            mastery.next_review_at = now
        else:
            self.db.add(MasteryRecordModel(
                id=str(uuid4()),
                user_id="anonymous",
                knowledge_unit_id=learned.unit_id,
                book_id=db_unit.book_id,
                mastery_score=0.3,
                mastery_level="beginner",
                review_count=0,
                last_reviewed_at=now,
                next_review_at=now,
            ))

        await self.db.flush()

    async def _update_knowledge_graph(self, book_id: str, learned: LearnedUnit) -> None:
        """学完一个单元后，增量更新知识图谱"""
        if self.db is None:
            return

        from app.modules.knowledge_graph.service import KnowledgeGraphService
        from app.modules.ai_learning.schemas import Concept

        svc = KnowledgeGraphService(self.db)

        # 构建 unit_data（兼容 GraphBuilder 的输入格式）
        concepts_data = []
        for c in learned.concepts:
            if isinstance(c, Concept):
                concepts_data.append({
                    "name": c.name, "definition": c.definition,
                    "examples": c.examples, "related_concepts": c.related_concepts,
                })
            else:
                concepts_data.append(c)

        unit_data = {
            "id": learned.unit_id,
            "title": learned.summary[:50] if learned.summary else "未命名",
            "concepts": concepts_data,
            "prerequisites": learned.prerequisites,
            "summary": learned.summary,
            "key_points": [{"title": kp.title, "explanation": kp.explanation, "examples": kp.examples}
                          for kp in learned.key_points],
            "difficulty_level": learned.difficulty_level,
            "importance_score": learned.importance_score,
        }

        try:
            await svc.update_unit_graph(book_id, unit_data)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"图谱增量更新失败: {e}")

    async def get_learning_order(
        self,
        book_id: str,
        units: List[KnowledgeUnit],
    ) -> List[KnowledgeUnit]:
        """
        基于知识图谱拓扑排序 + 前置掌握度，返回优化后的学习顺序。
        前置未掌握的单元自动排到前面。
        """
        if not self.db:
            return units

        from app.modules.knowledge_graph.service import KnowledgeGraphService
        kg_service = KnowledgeGraphService(self.db)

        try:
            ordered_ids = await kg_service.get_topological_order(book_id)
        except Exception:
            return units

        unit_map = {u.id: u for u in units}
        ordered = [unit_map[uid] for uid in ordered_ids if uid in unit_map]
        seen = {u.id for u in ordered}
        ordered.extend([u for u in units if u.id not in seen])
        return ordered

    async def learn_book(
        self,
        book_id: str,
        units: List[KnowledgeUnit],
        chapters: List[Chapter],
        on_progress: Optional[Callable] = None,
        force_relearn: bool = False,
    ) -> BookLearningResult:
        """对整本书进行AI学习（分层并发：同层内单元并行处理）

        Args:
            force_relearn: 是否强制重新学习已学习的单元
        """
        units = await self.get_learning_order(book_id, units)
        start_time = time.time()
        total_units = len(units)

        # 尝试获取拓扑分层
        layers = await self._get_topological_layers(book_id, units)

        learned_count = 0
        failed_count = 0
        skipped_count = 0
        total_token_cost = 0
        completed_summaries: List[str] = []
        completed_concepts: List[str] = []
        completed_index = 0  # 已完成的单元计数（用于进度）

        for layer_idx, layer_units in enumerate(layers):
            logger.info(f"开始处理第 {layer_idx + 1} 层（{len(layer_units)} 个单元）")

            # 构建上下文：使用前一层所有单元的摘要
            layer_context = "\n".join(completed_summaries[-5:]) if completed_summaries else None

            # 分离已学习和未学习的单元
            to_learn = []
            for unit in layer_units:
                if not force_relearn and unit.summary:
                    skipped_count += 1
                    completed_summaries.append(unit.summary)
                    if unit.key_points:
                        for kp in unit.key_points[:5]:
                            title = kp.get("title", "") if isinstance(kp, dict) else str(kp)
                            if title:
                                completed_concepts.append(title)
                    completed_index += 1
                    if on_progress:
                        on_progress(completed_index, total_units, f"[跳过] {unit.title}")
                else:
                    to_learn.append(unit)

            if not to_learn:
                continue

            # 检查 token 预算
            if self.token_budget and self._total_tokens_used >= self.token_budget:
                completed_index += len(to_learn)
                continue

            # 并发学习本层所有单元
            results = await self._learn_layer(
                to_learn, chapters, book_id, total_units,
                layer_context, completed_concepts,
                on_progress, completed_index,
            )

            for unit, result in results:
                if isinstance(result, Exception):
                    logger.error(f"[AI学习失败] 单元: {unit.title}", exc_info=result)
                    failed_count += 1
                    completed_index += 1
                    if on_progress:
                        on_progress(completed_index, total_units, f"[失败] {unit.title}")
                else:
                    completed_summaries.append(result.summary)
                    completed_concepts.extend([c.name for c in result.concepts])
                    self._total_tokens_used += result.token_cost
                    total_token_cost += result.token_cost
                    learned_count += 1
                    completed_index += 1
                    # 成功的单元已在 _learn_layer 内上报进度，此处不重复调用 on_progress

        # 批量学习完成后统一重建知识图谱（比逐单元更新快得多）
        if learned_count > 0 and self.db:
            if on_progress:
                on_progress(total_units, total_units, "正在重建知识图谱...")
            try:
                from app.modules.knowledge_graph.service import KnowledgeGraphService
                from app.db.models import KnowledgeUnitModel, ChapterModel, MasteryRecordModel
                from sqlalchemy import select

                # 重新加载最新数据
                units_result = await self.db.execute(
                    select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
                )
                db_units = units_result.scalars().all()
                chapters_result = await self.db.execute(
                    select(ChapterModel).where(ChapterModel.book_id == book_id)
                )
                db_chapters = chapters_result.scalars().all()
                mastery_result = await self.db.execute(
                    select(MasteryRecordModel).where(MasteryRecordModel.book_id == book_id)
                )
                db_mastery = mastery_result.scalars().all()

                kg_units = [
                    {"id": u.id, "title": u.title, "content": u.content or "",
                     "concepts": json.loads(u.concepts) if u.concepts else [],
                     "prerequisites": json.loads(u.prerequisites) if u.prerequisites else [],
                     "summary": u.summary or "", "key_points": json.loads(u.key_points) if u.key_points else [],
                     "difficulty_level": u.difficulty_level or 3, "importance_score": u.importance_score or 0.5,
                     "chapter_id": u.chapter_id}
                    for u in db_units
                ]
                kg_chapters = [
                    {"id": c.id, "title": c.title, "chapter_number": c.chapter_number or 0,
                     "order_index": c.order_index or 0, "book_id": c.book_id}
                    for c in db_chapters
                ]
                kg_mastery = [
                    {"knowledge_unit_id": m.knowledge_unit_id, "mastery_score": m.mastery_score,
                     "mastery_level": m.mastery_level}
                    for m in db_mastery
                ]

                kg_service = KnowledgeGraphService(self.db)
                await kg_service.build_graph(book_id, kg_units, kg_chapters, kg_mastery)
                logger.info(f"知识图谱重建完成（{learned_count} 个新单元）")
            except Exception as e:
                logger.warning(f"知识图谱重建失败（不影响学习结果）: {e}")

        return BookLearningResult(
            book_id=book_id,
            total_units=total_units,
            learned_count=learned_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            total_token_cost=total_token_cost,
            duration_seconds=time.time() - start_time,
        )

    async def _get_topological_layers(
        self, book_id: str, units: List[KnowledgeUnit]
    ) -> List[List[KnowledgeUnit]]:
        """获取拓扑分层，失败时退化为单层（全部一起处理）"""
        unit_map = {u.id: u for u in units}
        try:
            from app.modules.knowledge_graph.service import KnowledgeGraphService
            kg_service = KnowledgeGraphService(self.db)
            id_layers = await kg_service.get_topological_layers(book_id)
            layers = []
            for id_layer in id_layers:
                layer = [unit_map[uid] for uid in id_layer if uid in unit_map]
                if layer:
                    layers.append(layer)
            # 拓扑排序未覆盖的单元放到最后一层
            ordered_ids = {u.id for layer in layers for u in layer}
            remaining = [u for u in units if u.id not in ordered_ids]
            if remaining:
                layers.append(remaining)
            return layers if layers else [units]
        except Exception:
            return [units]

    async def _learn_layer(
        self,
        layer_units: List[KnowledgeUnit],
        chapters: List[Chapter],
        book_id: str,
        total_units: int,
        layer_context: Optional[str],
        existing_concepts: List[str],
        on_progress: Optional[Callable],
        base_index: int,
    ) -> List[tuple]:
        """分批并发学习一层内的所有单元，返回 [(unit, result_or_exception), ...]"""
        # 每批最多 MAX_CONCURRENT 个单元并发，避免一个卡住拖垮全部
        max_concurrent = 4
        all_results: List[tuple] = []
        # 已完成计数器（单线程 asyncio 安全，无需锁）
        completed_count = base_index

        for batch_start in range(0, len(layer_units), max_concurrent):
            batch = layer_units[batch_start:batch_start + max_concurrent]

            async def _learn_one(unit: KnowledgeUnit, idx: int):
                nonlocal completed_count
                context = self.optimizer.build_context(
                    unit, chapters, layer_context, existing_concepts
                )
                def _wrap_progress(cur: float, _total: int, msg: str):
                    if on_progress is None:
                        return
                    if 0 <= cur < 1:
                        # 子单元进度：用当前已完成数作为基准（确保不后退）
                        on_progress(completed_count + cur, total_units, msg)
                    else:
                        on_progress(cur, _total, msg)
                # 每个单元最多 300 秒（与 httpx 超时一致），超时则跳过
                try:
                    result = await asyncio.wait_for(
                        self.learn_unit(unit, context, on_progress=_wrap_progress),
                        timeout=300,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"单元「{unit.title}」学习超时（300秒），跳过")
                    raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, f"单元「{unit.title}」LLM 调用超时")
                # 单元完成，立即上报进度（不等整个 batch 结束）
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total_units, unit.title)
                return result

            tasks = [_learn_one(unit, batch_start + i) for i, unit in enumerate(batch)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(zip(batch, batch_results))

        return all_results

    def _build_context_info(self, context: LearningContext, iteration: int) -> str:
        """构建上下文描述"""
        parts = []
        if iteration > 0:
            parts.append(f"这是第{iteration + 1}次深化学习，请重点关注之前识别的薄弱点。")
        if context.previous_unit_summary:
            parts.append(f"前一个知识点摘要：{context.previous_unit_summary}")
        if context.chapter_summary:
            parts.append(f"当前章节概述：{context.chapter_summary}")
        if context.existing_concepts:
            parts.append(f"已学概念：{', '.join(context.existing_concepts[:10])}")
        return "\n".join(parts) if parts else "无额外上下文"

    async def relearn_unit(self, unit: KnowledgeUnit) -> LearnedUnit:
        """
        重新生成指定知识单元的 AI 分析。
        直接用原文重新调 LLM，覆盖旧结果。适用于对生成结果不满意的情况。
        """
        context_info = self._build_context_info(LearningContext(), 0)
        prompt = build_understand_prompt(
            content=unit.content,
            context_info=context_info,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=16384,
        )
        understand_result = self._extract_json(response.content)

        # 质量校验：失败则重试一次
        if not self._validate_parsed_result(understand_result):
            logger.warning(f"单元「{unit.title}」重新学习结果质量不合格，重试...")
            response = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=16384,
            )
            understand_result = self._extract_json(response.content)
        concepts = [Concept(**c) for c in understand_result.get("concepts", [])]
        raw_kps = self._normalize_key_points(understand_result.get("key_points", []))
        key_points = [KeyPoint(**kp) for kp in raw_kps]
        learned = LearnedUnit(
            unit_id=unit.id,
            book_id=unit.book_id,
            summary=understand_result.get("summary", ""),
            explanation=understand_result.get("explanation", ""),
            key_points=key_points,
            concepts=concepts,
            difficulty_level=understand_result.get("difficulty_level", 3),
            importance_score=understand_result.get("importance_score", 0.5),
            prerequisites=understand_result.get("prerequisites", []),
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=(response.usage or {}).get("total_tokens", 0),
        )
        await self._persist_learned_unit(learned)
        return learned

    async def enrich_unit(
        self,
        unit_id: str,
        book_id: str,
        chapter_id: str,
        title: str,
        content: str,
        existing_summary: str,
        existing_key_points: list,
        existing_concepts: list,
        existing_explanation: str = "",
        existing_difficulty_level: int = 3,
        existing_importance_score: float = 0.5,
        existing_prerequisites: list | None = None,
        focus: str | None = None,
        instruction: str | None = None,
    ) -> LearnedUnit:
        """
        增量更新知识单元。在原有分析基础上补充细节，不覆盖。

        聚焦模式（focus 有值）：prompt 只要求返回目标字段，合并时只更新该字段。
        通用模式（focus 无值）：返回全部字段，全部合并。
        """
        if existing_prerequisites is None:
            existing_prerequisites = []

        # 统一 existing_key_points 为 dict 列表
        norm_existing_kps = self._normalize_key_points(existing_key_points)

        # 构建补充指令
        if focus and focus in FOCUS_DIRECTIONS:
            enrich_instruction = FOCUS_DIRECTIONS[focus]["instruction"]
        else:
            enrich_instruction = "请基于以下原文和已有的分析结果，补充缺失的细节。"
        if instruction:
            enrich_instruction += f"\n\n补充要求：{instruction}"

        prompt = build_enrich_prompt(
            title=title,
            content=content,
            existing_summary=existing_summary,
            existing_key_points=existing_key_points,
            existing_concepts=existing_concepts,
            instruction=enrich_instruction,
            focus=focus,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.4,
            max_tokens=16384,
        )
        enriched = self._extract_json(response.content)

        # 确定本次更新的目标字段
        target_fields = FOCUS_DIRECTIONS.get(focus, {}).get("fields") if focus else None

        if target_fields:
            # 聚焦模式：只更新目标字段，其余保留旧值
            merged_summary = existing_summary
            merged_explanation = existing_explanation
            merged_points = norm_existing_kps
            concepts_raw = existing_concepts
            merged_diff = existing_difficulty_level
            merged_imp = existing_importance_score
            merged_prereqs = existing_prerequisites

            if "summary" in target_fields:
                merged_summary = enriched.get("summary") or existing_summary
            if "explanation" in target_fields:
                merged_explanation = enriched.get("explanation") or existing_explanation
            if "key_points" in target_fields:
                new_points = self._normalize_key_points(enriched.get("key_points", []))
                if new_points:
                    seen = {kp.get("title", "") for kp in new_points}
                    merged_points = new_points + [kp for kp in norm_existing_kps if kp.get("title", "") not in seen]
                else:
                    merged_points = norm_existing_kps
            if "concepts" in target_fields:
                new_concepts_raw = enriched.get("concepts", [])
                if new_concepts_raw:
                    existing_by_name = {c.get("name", ""): c for c in existing_concepts}
                    new_by_name = {c.get("name", ""): c for c in new_concepts_raw if isinstance(c, dict)}
                    merged_map = {**existing_by_name, **new_by_name}
                    concepts_raw = list(merged_map.values())
        else:
            # 通用模式：全部字段合并，LLM 新值有内容则取新值，否则保留旧值
            merged_summary = enriched.get("summary") or existing_summary
            merged_explanation = enriched.get("explanation") or existing_explanation
            new_points = self._normalize_key_points(enriched.get("key_points", []))
            seen = {kp.get("title", "") for kp in new_points}
            merged_points = new_points + [kp for kp in norm_existing_kps if kp.get("title", "") not in seen]
            existing_by_name = {c.get("name", ""): c for c in existing_concepts}
            new_by_name = {c.get("name", c if isinstance(c, str) else c.get("name", "")): c
                           for c in enriched.get("concepts", [])}
            merged_map = {**existing_by_name, **new_by_name}
            concepts_raw = list(merged_map.values())
            new_diff = enriched.get("difficulty_level")
            new_imp = enriched.get("importance_score")
            merged_diff = new_diff if new_diff is not None else existing_difficulty_level
            merged_imp = new_imp if new_imp is not None else existing_importance_score
            merged_prereqs = enriched.get("prerequisites") or existing_prerequisites

        # 构建 Concept 对象
        concepts = [Concept(**c) if isinstance(c, dict) else Concept(name=c, definition="")
                    for c in concepts_raw if c]

        # 构建 KeyPoint 对象
        key_points = [KeyPoint(**kp) for kp in merged_points]

        learned = LearnedUnit(
            unit_id=unit_id,
            book_id=book_id,
            summary=merged_summary,
            explanation=merged_explanation,
            key_points=key_points,
            concepts=concepts,
            difficulty_level=merged_diff,
            importance_score=merged_imp,
            prerequisites=merged_prereqs,
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=(response.usage or {}).get("total_tokens", 0),
        )
        await self._persist_learned_unit(learned)
        return learned


class SelectiveLearningService:
    """选择性学习服务"""

    def __init__(self, llm_client: LLMClient, db_session=None):
        self.learning_service = AILearningService(llm_client, db_session)

    def get_book_overview(
        self,
        book_id: str,
        chapters: List[Chapter],
        units: List[KnowledgeUnit],
    ) -> BookOverview:
        """生成书籍概览"""
        chapter_overviews = []
        for chapter in chapters:
            chapter_units = [u for u in units if u.chapter_id == chapter.id]
            avg_difficulty = sum(
                u.difficulty_level or 3 for u in chapter_units
            ) / max(len(chapter_units), 1)
            chapter_overviews.append(
                ChapterOverview(
                    chapter_id=chapter.id,
                    title=chapter.title,
                    key_concepts_preview=[],  # 需要AI学习后填充
                    estimated_minutes=len(chapter_units) * 12,
                    difficulty_level=round(avg_difficulty),
                    unit_count=len(chapter_units),
                )
            )

        return BookOverview(
            book_id=book_id,
            title="",
            total_chapters=len(chapters),
            chapters=chapter_overviews,
        )

    async def learn_selected(
        self,
        book_id: str,
        chapter_ids: List[str],
        units: List[KnowledgeUnit],
        chapters: List[Chapter],
        on_progress: Optional[Callable] = None,
    ) -> BookLearningResult:
        """只学习用户选择的章节"""
        # 过滤选中章节的单元
        selected_units = [u for u in units if u.chapter_id in chapter_ids]
        selected_chapters = [c for c in chapters if c.id in chapter_ids]

        if not selected_units:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "选中的章节没有知识单元")

        return await self.learning_service.learn_book(
            book_id, selected_units, selected_chapters, on_progress
        )
