"""学习方案服务"""
import json
from typing import List, Optional

from sqlalchemy import select

from app.modules.learning_plan.schemas import (
    LearningStyle, LearningPlan, PlanSession, Milestone,
    SessionPerformance, PlanUpdate,
)
from app.modules.learning_plan.style_analyzer import LearningStyleAnalyzer
from app.modules.ai_learning.schemas import LearnedUnit
from app.common.errors import ServiceError, ErrorCode
from app.db.models import KnowledgeUnitModel, LearningRecordModel, UserModel

# ===== 可配置常量 =====

# 按难度的学习时间估算（分钟）
DIFFICULTY_TIME_MAP = {
    1: 5,   # 入门级
    2: 8,   # 基础
    3: 12,  # 中等
    4: 18,  # 进阶
    5: 25,  # 高级
}
DEFAULT_UNIT_TIME = 12  # 未知难度的默认时间

# 会话时间上限 = 每日目标 × 此倍数
SESSION_OVERSIZE_FACTOR = 1.5

# 里程碑间隔计算：总会话数 // 此值，至少为 2
MILESTONE_DIVISOR = 3
MIN_MILESTONE_INTERVAL = 2

# 低性能阈值
LOW_PERFORMANCE_THRESHOLD = 0.5


class LearningPlanService:
    """学习方案服务"""

    def __init__(self, style_analyzer: LearningStyleAnalyzer, db_session=None):
        self.style_analyzer = style_analyzer
        self.db = db_session

    async def generate_plan(self, user_id: str, book_id: str,
                            units: List[LearnedUnit],
                            daily_goal_minutes: int = 30) -> LearningPlan:
        """
        为用户生成个性化学习方案。

        流程：
        1. 获取用户学习风格
        2. 根据学习风格和每日目标，将单元分组成会话
        3. 为每个会话推荐教学策略
        4. 设置里程碑
        """
        style = await self.style_analyzer.get_style(user_id)
        sessions = self._group_units_into_sessions(units, style, daily_goal_minutes)
        total_minutes = sum(s.estimated_minutes for s in sessions)
        milestones = self._create_milestones(sessions)

        return LearningPlan(
            book_id=book_id,
            user_id=user_id,
            sessions=sessions,
            total_estimated_minutes=total_minutes,
            milestones=milestones,
            style_snapshot=style,
            daily_goal_minutes=daily_goal_minutes,
        )

    def _group_units_into_sessions(self, units: List[LearnedUnit],
                                    style: LearningStyle,
                                    daily_goal_minutes: int) -> List[PlanSession]:
        """将知识单元分组成学习会话"""
        sessions: List[PlanSession] = []
        current_unit_ids: List[str] = []
        current_minutes = 0
        session_number = 1
        limit = daily_goal_minutes * SESSION_OVERSIZE_FACTOR

        # 快节奏：放宽时间上限，让每个会话装更多单元
        if style.fast_paced:
            limit *= 1.5

        for unit in units:
            unit_minutes = DIFFICULTY_TIME_MAP.get(unit.difficulty_level, DEFAULT_UNIT_TIME)

            if current_unit_ids and current_minutes + unit_minutes > limit:
                sessions.append(self._create_session(
                    session_number, current_unit_ids, current_minutes, style
                ))
                session_number += 1
                current_unit_ids = []
                current_minutes = 0

            current_unit_ids.append(unit.unit_id)
            current_minutes += unit_minutes

        if current_unit_ids:
            sessions.append(self._create_session(
                session_number, current_unit_ids, current_minutes, style
            ))

        return sessions

    def _create_session(self, session_number: int, unit_ids: List[str],
                        estimated_minutes: int, style: LearningStyle) -> PlanSession:
        """创建单个会话"""
        if style.example_heavy:
            strategy = "example_first"
        elif style.theory_first:
            strategy = "theory_first"
        elif style.problem_based:
            strategy = "problem_based"
        else:
            strategy = "balanced"

        return PlanSession(
            session_number=session_number,
            unit_ids=unit_ids,
            estimated_minutes=estimated_minutes,
            teaching_strategy=strategy,
        )

    def _create_milestones(self, sessions: List[PlanSession]) -> List[Milestone]:
        """创建里程碑（间隔至少为2，避免每个会话都是里程碑）"""
        if not sessions:
            return []

        interval = max(MIN_MILESTONE_INTERVAL, len(sessions) // MILESTONE_DIVISOR)
        milestones = []
        total = len(sessions)

        for i in range(0, total, interval):
            end_idx = min(i + interval, total)
            milestones.append(Milestone(
                title=f"完成阶段 {len(milestones) + 1}",
                session_indices=list(range(i, end_idx)),
                reward_description=f"已完成 {end_idx}/{total} 个学习会话",
            ))

        return milestones

    def get_current_session(self, plan: LearningPlan,
                           completed_sessions: int) -> Optional[PlanSession]:
        """获取当前应该学习的会话"""
        if completed_sessions < len(plan.sessions):
            return plan.sessions[completed_sessions]
        return None

    async def complete_session(self, plan: LearningPlan,
                               session_id: str,
                               performance: SessionPerformance) -> PlanUpdate:
        """标记会话完成，更新进度并持久化记录"""
        current_idx = None
        for i, session in enumerate(plan.sessions):
            if session.id == session_id:
                current_idx = i
                break

        if current_idx is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "会话不存在")

        # 持久化学习记录到数据库
        if self.db is not None:
            record = LearningRecordModel(
                user_id=plan.user_id,
                book_id=plan.book_id,
                session_id=session_id,
                duration_minutes=performance.duration_minutes,
                questions_asked=performance.questions_asked,
                test_score=performance.correct_rate * 100,
                units_covered=json.dumps(plan.sessions[current_idx].unit_ids),
            )
            self.db.add(record)

            # 更新用户学习风格
            from app.modules.learning_plan.schemas import SessionData
            session_data = SessionData(
                question_count=performance.questions_asked,
                practice_correct_rate=performance.correct_rate,
                practice_speed=performance.duration_minutes / max(
                    plan.sessions[current_idx].estimated_minutes, 1
                ),
            )
            await self.style_analyzer.update_from_session(plan.user_id, session_data)
            await self.db.flush()

        # 检查里程碑
        milestone_reached = None
        for milestone in plan.milestones:
            if current_idx in milestone.session_indices:
                if all(idx <= current_idx for idx in milestone.session_indices):
                    milestone_reached = milestone
                    break

        next_session = None
        if current_idx + 1 < len(plan.sessions):
            next_session = plan.sessions[current_idx + 1]

        adjusted = performance.correct_rate < LOW_PERFORMANCE_THRESHOLD
        reason = "正确率较低，建议复习" if adjusted else None

        return PlanUpdate(
            adjusted=adjusted,
            reason=reason,
            next_session=next_session,
            milestone_reached=milestone_reached,
        )

    @staticmethod
    async def load_units_from_db(db, book_id: str) -> List[LearnedUnit]:
        """从数据库加载知识单元，转换为 LearnedUnit"""
        from app.modules.ai_learning.schemas import Concept, SelfAssessment

        result = await db.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .order_by(KnowledgeUnitModel.order_index)
        )
        db_units = list(result.scalars().all())

        units = []
        for u in db_units:
            # 解析 concepts JSON
            concepts = []
            if u.concepts:
                try:
                    raw = json.loads(u.concepts)
                    for c in raw:
                        if isinstance(c, dict):
                            concepts.append(Concept(**c))
                        else:
                            concepts.append(Concept(name=str(c), definition=""))
                except (json.JSONDecodeError, TypeError):
                    pass

            # 解析 prerequisites JSON
            prerequisites = []
            if u.prerequisites:
                try:
                    prerequisites = json.loads(u.prerequisites)
                except (json.JSONDecodeError, TypeError):
                    pass

            units.append(LearnedUnit(
                unit_id=u.id,
                book_id=u.book_id,
                summary=u.summary or "",
                key_points=u.key_points.split(",") if u.key_points else [],
                concepts=concepts,
                difficulty_level=u.difficulty_level or 3,
                importance_score=u.importance_score or 0.5,
                prerequisites=prerequisites,
                self_assessment=SelfAssessment(
                    score=0,
                    test_questions=[],
                    self_answers=[],
                    weak_points=[],
                    needs_deepening=False,
                ),
            ))
        return units
