"""教学计划系统 - 确保知识覆盖完整性

设计理念：
- 教学前：生成教学计划，列出所有必须覆盖的内容
- 教学中：实时追踪覆盖情况
- 教学后：验证覆盖率，未达 100% 则补充教学

严格模式：100% 覆盖才能完成教学
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
from enum import Enum
from datetime import datetime

from app.modules.ai_learning.schemas import LearnedUnit, KeyPoint, Concept


class CoverageStatus(str, Enum):
    """覆盖状态"""
    NOT_STARTED = "not_started"      # 未开始
    IN_PROGRESS = "in_progress"      # 进行中
    COMPLETED = "completed"          # 已完成
    NEEDS_REVIEW = "needs_review"    # 需要复习


@dataclass
class ContentItem:
    """内容项 - 需要覆盖的知识点"""
    id: str                          # 唯一标识
    content_type: str                # "key_point" | "concept" | "example"
    title: str                       # 标题
    content: str                     # 内容
    importance: float = 1.0          # 重要性权重 (0-1)
    is_covered: bool = False         # 是否已覆盖
    covered_in_phase: Optional[str] = None  # 在哪个阶段覆盖的
    covered_at: Optional[datetime] = None   # 覆盖时间


@dataclass
class PhasePlan:
    """阶段计划 - 每个阶段的覆盖任务"""
    phase: str                       # 教学阶段
    description: str                 # 阶段描述
    target_items: List[str]          # 本阶段必须覆盖的内容ID
    completed_items: Set[str] = field(default_factory=set)  # 已完成的内容ID

    @property
    def is_complete(self) -> bool:
        """本阶段是否完成"""
        return set(self.target_items) <= self.completed_items

    @property
    def coverage_rate(self) -> float:
        """本阶段覆盖率"""
        if not self.target_items:
            return 1.0
        return len(self.completed_items) / len(self.target_items)


@dataclass
class TeachingPlan:
    """教学计划 - 确保知识覆盖完整"""
    unit_id: str
    book_id: str
    unit_summary: str

    # 所有需要覆盖的内容
    content_items: Dict[str, ContentItem] = field(default_factory=dict)

    # 教学阶段计划
    phase_plans: List[PhasePlan] = field(default_factory=list)

    # 当前阶段索引
    current_phase_index: int = 0

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_items(self) -> int:
        """总内容项数"""
        return len(self.content_items)

    @property
    def covered_items(self) -> int:
        """已覆盖的内容项数"""
        return sum(1 for item in self.content_items.values() if item.is_covered)

    @property
    def coverage_rate(self) -> float:
        """总覆盖率"""
        if not self.content_items:
            return 1.0
        return self.covered_items / self.total_items

    @property
    def is_complete(self) -> bool:
        """教学计划是否完成（严格模式：100%覆盖）"""
        return self.coverage_rate >= 1.0

    @property
    def current_phase(self) -> Optional[PhasePlan]:
        """当前阶段计划"""
        if 0 <= self.current_phase_index < len(self.phase_plans):
            return self.phase_plans[self.current_phase_index]
        return None

    def get_missing_items(self) -> List[ContentItem]:
        """获取未覆盖的内容项"""
        return [item for item in self.content_items.values() if not item.is_covered]

    def get_phase_missing_items(self, phase: str) -> List[ContentItem]:
        """获取指定阶段未覆盖的内容项"""
        phase_plan = next((p for p in self.phase_plans if p.phase == phase), None)
        if not phase_plan:
            return []

        return [
            self.content_items[item_id]
            for item_id in phase_plan.target_items
            if item_id not in phase_plan.completed_items
        ]


class TeachingPlanGenerator:
    """教学计划生成器"""

    def generate_plan(self, unit: LearnedUnit, book_id: str) -> TeachingPlan:
        """为知识单元生成教学计划"""
        plan = TeachingPlan(
            unit_id=unit.unit_id,
            book_id=book_id,
            unit_summary=unit.summary,
        )

        # 1. 提取所有需要覆盖的内容项
        self._extract_content_items(unit, plan)

        # 2. 生成阶段计划
        self._generate_phase_plans(unit, plan)

        return plan

    def _extract_content_items(self, unit: LearnedUnit, plan: TeachingPlan):
        """提取所有需要覆盖的内容项"""

        # 提取关键要点
        for i, kp in enumerate(unit.key_points):
            item_id = f"kp_{i}"
            plan.content_items[item_id] = ContentItem(
                id=item_id,
                content_type="key_point",
                title=kp.title,
                content=kp.explanation or kp.title,
                importance=1.0,  # 关键要点默认最高重要性
            )

            # 提取要点的例子
            for j, example in enumerate(kp.examples):
                example_id = f"kp_{i}_ex_{j}"
                plan.content_items[example_id] = ContentItem(
                    id=example_id,
                    content_type="example",
                    title=f"{kp.title}的例子",
                    content=example,
                    importance=0.8,
                )

        # 提取核心概念
        for i, concept in enumerate(unit.concepts):
            item_id = f"concept_{i}"
            plan.content_items[item_id] = ContentItem(
                id=item_id,
                content_type="concept",
                title=concept.name,
                content=concept.definition,
                importance=1.0,  # 核心概念默认最高重要性
            )

            # 提取概念的例子
            for j, example in enumerate(concept.examples):
                example_id = f"concept_{i}_ex_{j}"
                plan.content_items[example_id] = ContentItem(
                    id=example_id,
                    content_type="example",
                    title=f"{concept.name}的例子",
                    content=example,
                    importance=0.8,
                )

            # 提取相关概念
            for j, related in enumerate(concept.related_concepts):
                related_id = f"concept_{i}_related_{j}"
                plan.content_items[related_id] = ContentItem(
                    id=related_id,
                    content_type="concept",
                    title=f"{concept.name}的相关概念",
                    content=related,
                    importance=0.6,
                )

    def _generate_phase_plans(self, unit: LearnedUnit, plan: TeachingPlan):
        """生成阶段计划"""

        # 获取所有内容项ID
        key_point_ids = [k for k in plan.content_items.keys() if k.startswith("kp_") and "_ex_" not in k]
        concept_ids = [k for k in plan.content_items.keys() if k.startswith("concept_") and "_ex_" not in k and "_related_" not in k]
        example_ids = [k for k in plan.content_items.keys() if "_ex_" in k]
        related_ids = [k for k in plan.content_items.keys() if "_related_" in k]

        # 阶段 1: ACTIVATE - 激活先验知识
        plan.phase_plans.append(PhasePlan(
            phase="activate",
            description="激活先验知识，建立学习动机",
            target_items=[],  # 激活阶段不覆盖新内容
        ))

        # 阶段 2: INTRO - 导览
        plan.phase_plans.append(PhasePlan(
            phase="intro",
            description="概述学习目标和内容框架",
            target_items=key_point_ids[:2] if len(key_point_ids) > 2 else key_point_ids,  # 预览前2个要点
        ))

        # 阶段 3: CORE - 讲解核心内容
        plan.phase_plans.append(PhasePlan(
            phase="core",
            description="核心内容的详细讲解",
            target_items=key_point_ids + concept_ids,  # 必须覆盖所有要点和概念
        ))

        # 阶段 4: EXAMPLE - 示例说明
        plan.phase_plans.append(PhasePlan(
            phase="example",
            description="通过例子加深理解",
            target_items=example_ids,  # 覆盖所有例子
        ))

        # 阶段 5: FEYNMAN - 费曼学习法
        plan.phase_plans.append(PhasePlan(
            phase="feynman",
            description="用自己的话解释，检验真正理解",
            target_items=key_point_ids,  # 用费曼法覆盖所有要点
        ))

        # 阶段 6: RETRIEVAL - 检索练习
        plan.phase_plans.append(PhasePlan(
            phase="retrieval",
            description="主动回忆练习，强化记忆",
            target_items=key_point_ids + concept_ids,  # 检索所有要点和概念
        ))

        # 阶段 7: CHECK - 理解检测
        plan.phase_plans.append(PhasePlan(
            phase="check",
            description="理解检测，发现知识盲点",
            target_items=key_point_ids + concept_ids,  # 检测所有要点和概念
        ))

        # 阶段 8: REFLECT - 反思
        plan.phase_plans.append(PhasePlan(
            phase="reflect",
            description="元认知反思，总结学习收获",
            target_items=related_ids,  # 反思阶段覆盖相关概念
        ))

        # 阶段 9: CONNECT - 联结
        plan.phase_plans.append(PhasePlan(
            phase="connect",
            description="建立知识网络，关联已有知识",
            target_items=related_ids,  # 联结阶段覆盖相关概念
        ))


class CoverageTracker:
    """覆盖追踪器 - 实时追踪教学覆盖情况"""

    def __init__(self):
        # 关键词到内容项的映射
        self._keyword_map: Dict[str, List[str]] = {}

    def initialize(self, plan: TeachingPlan):
        """初始化追踪器"""
        self._keyword_map.clear()

        # 构建关键词映射
        for item_id, item in plan.content_items.items():
            # 从标题和内容中提取关键词
            keywords = self._extract_keywords(item.title)
            keywords.update(self._extract_keywords(item.content))

            for keyword in keywords:
                if keyword not in self._keyword_map:
                    self._keyword_map[keyword] = []
                self._keyword_map[keyword].append(item_id)

    def track_message(self, plan: TeachingPlan, message: str, phase: str):
        """分析教学消息，更新覆盖追踪"""
        # 提取消息中的关键词
        message_keywords = self._extract_keywords(message)

        # 查找匹配的内容项
        covered_items = set()
        for keyword in message_keywords:
            if keyword in self._keyword_map:
                covered_items.update(self._keyword_map[keyword])

        # 更新覆盖状态
        for item_id in covered_items:
            if item_id in plan.content_items:
                item = plan.content_items[item_id]
                if not item.is_covered:
                    item.is_covered = True
                    item.covered_in_phase = phase
                    item.covered_at = datetime.now()

        # 更新阶段计划
        phase_plan = next((p for p in plan.phase_plans if p.phase == phase), None)
        if phase_plan:
            phase_plan.completed_items.update(covered_items)

    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词（简单的中文分词）"""
        import re

        # 移除标点符号和特殊字符
        text = re.sub(r'[^\w\s]', ' ', text)

        # 简单的分词：按空格和常见分隔符分割
        words = set()

        # 英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        words.update(w.lower() for w in english_words if len(w) > 2)

        # 中文：提取2-4字的词组
        chinese_chars = re.findall(r'[一-鿿]+', text)
        for chars in chinese_chars:
            # 2字词
            for i in range(len(chars) - 1):
                words.add(chars[i:i+2])
            # 3字词
            for i in range(len(chars) - 2):
                words.add(chars[i:i+3])
            # 4字词
            for i in range(len(chars) - 3):
                words.add(chars[i:i+4])

        return words

    def get_coverage_report(self, plan: TeachingPlan) -> Dict:
        """获取覆盖报告"""
        missing_items = plan.get_missing_items()

        return {
            "unit_id": plan.unit_id,
            "total_items": plan.total_items,
            "covered_items": plan.covered_items,
            "coverage_rate": plan.coverage_rate,
            "is_complete": plan.is_complete,
            "missing_items": [
                {
                    "id": item.id,
                    "type": item.content_type,
                    "title": item.title,
                }
                for item in missing_items
            ],
            "phase_coverage": [
                {
                    "phase": phase.phase,
                    "description": phase.description,
                    "coverage_rate": phase.coverage_rate,
                    "is_complete": phase.is_complete,
                }
                for phase in plan.phase_plans
            ],
        }


# 全局实例
plan_generator = TeachingPlanGenerator()
coverage_tracker = CoverageTracker()
