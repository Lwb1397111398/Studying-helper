"""学习风格分析器"""
import json
from typing import Optional

from sqlalchemy import select, func

from app.modules.learning_plan.schemas import LearningStyle, SessionData
from app.db.models import LearningRecordModel, DailyStatsModel, UserModel


class LearningStyleAnalyzer:
    """学习风格分析器"""

    DEFAULT_STYLE = LearningStyle()
    MIN_SESSIONS_FOR_ANALYSIS = 10

    def __init__(self, db_session=None):
        self.db = db_session

    async def get_style(self, user_id: str) -> LearningStyle:
        """
        获取用户学习风格。

        策略：
        - 有足够历史数据 -> 基于数据分析
        - 数据不足 -> 返回默认风格 + 低置信度
        """
        if self.db is None:
            return LearningStyle()

        # 先查用户表中是否已有缓存的学习风格
        user_result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return LearningStyle()

        if user.learning_style_json:
            try:
                cached = json.loads(user.learning_style_json)
                style = LearningStyle(**cached)
                if style.confidence >= 0.5:
                    return style
            except (json.JSONDecodeError, ValueError):
                pass

        # 从历史记录分析
        record_count = await self._count_records(user_id)
        if record_count < self.MIN_SESSIONS_FOR_ANALYSIS:
            style = LearningStyle(confidence=self._calculate_confidence(record_count))
            return style

        style = await self._analyze_from_records(user_id)
        await self._save_style(user_id, style)
        return style

    async def update_from_session(self, user_id: str, session_data: SessionData):
        """
        从学习会话数据更新学习风格。

        使用指数移动平均更新各维度分数。
        """
        if self.db is None:
            return

        current = await self.get_style(user_id)
        alpha = 0.3  # 新数据权重

        # 根据答题速度推断节奏偏好
        if session_data.practice_speed > 1.2:
            current.fast_paced = True
            current.step_by_step = False
        elif session_data.practice_speed < 0.8:
            current.fast_paced = False
            current.step_by_step = True

        # 根据正确率调整内容偏好
        if session_data.practice_correct_rate > 0.8:
            current.example_heavy = True
        elif session_data.practice_correct_rate < 0.4:
            current.problem_based = True

        # 根据交互频次调整交互偏好
        if session_data.question_count > 5:
            current.interactive = True
        elif session_data.question_count == 0:
            current.self_paced = True
            current.interactive = False

        # 根据浏览内容类型调整信息接收偏好
        if session_data.content_types_viewed:
            total = sum(session_data.content_types_viewed.values())
            if total > 0:
                current.visual_score = session_data.content_types_viewed.get("visual", 0) / total
                current.auditory_score = session_data.content_types_viewed.get("audio", 0) / total
                current.reading_score = session_data.content_types_viewed.get("text", 0) / total
                current.kinesthetic_score = session_data.content_types_viewed.get("practice", 0) / total

        current.confidence = min(1.0, current.confidence + alpha * 0.1)
        await self._save_style(user_id, current)

    def _calculate_confidence(self, session_count: int) -> float:
        """计算置信度"""
        return min(1.0, session_count / self.MIN_SESSIONS_FOR_ANALYSIS)

    async def _count_records(self, user_id: str) -> int:
        """统计用户学习记录数"""
        result = await self.db.execute(
            select(func.count()).select_from(LearningRecordModel)
            .where(LearningRecordModel.user_id == user_id)
        )
        return result.scalar() or 0

    async def _analyze_from_records(self, user_id: str) -> LearningStyle:
        """从历史记录分析学习风格"""
        # 获取最近的学习记录
        result = await self.db.execute(
            select(LearningRecordModel)
            .where(LearningRecordModel.user_id == user_id)
            .order_by(LearningRecordModel.started_at.desc())
            .limit(50)
        )
        records = list(result.scalars().all())

        if not records:
            return self.DEFAULT_STYLE

        total = len(records)
        avg_duration = sum(r.duration_minutes or 0 for r in records) / total
        avg_questions = sum(r.questions_asked or 0 for r in records) / total
        avg_score = sum(r.test_score or 0 for r in records if r.test_score) / max(
            sum(1 for r in records if r.test_score), 1
        )

        # 获取每日统计
        stats_result = await self.db.execute(
            select(DailyStatsModel)
            .where(DailyStatsModel.user_id == user_id)
            .order_by(DailyStatsModel.date.desc())
            .limit(30)
        )
        stats = list(stats_result.scalars().all())

        # 分析节奏：平均时长 > 40分钟 → 快节奏
        fast_paced = avg_duration > 40
        step_by_step = avg_duration < 25

        # 分析内容偏好：高正确率 → 爱举例；低正确率 → 问题导向
        example_heavy = avg_score > 70
        problem_based = avg_score < 50

        # 分析交互偏好：提问多 → 互动式
        interactive = avg_questions > 3
        self_paced = avg_questions < 1

        # 分析信息接收偏好（基于学习时间和测试分数的分布）
        if stats:
            total_minutes = sum(s.total_minutes or 0 for s in stats)
            total_units = sum(s.units_learned or 0 for s in stats)
            total_reviews = sum(s.units_reviewed or 0 for s in stats)
            total_tests = sum(s.tests_taken or 0 for s in stats)
            denom = max(total_units + total_reviews + total_tests, 1)
            reading_score = total_units / denom
            kinesthetic_score = total_tests / denom
            visual_score = total_reviews / denom
            auditory_score = 1.0 - reading_score - kinesthetic_score - visual_score
            auditory_score = max(0.0, auditory_score)
        else:
            visual_score = auditory_score = reading_score = kinesthetic_score = 0.25

        return LearningStyle(
            visual_score=round(visual_score, 2),
            auditory_score=round(auditory_score, 2),
            reading_score=round(reading_score, 2),
            kinesthetic_score=round(kinesthetic_score, 2),
            fast_paced=fast_paced,
            step_by_step=step_by_step,
            holistic=not fast_paced and not step_by_step,
            example_heavy=example_heavy,
            theory_first=not example_heavy and not problem_based,
            problem_based=problem_based,
            interactive=interactive,
            self_paced=self_paced,
            confidence=self._calculate_confidence(total),
        )

    async def _save_style(self, user_id: str, style: LearningStyle):
        """保存学习风格到用户表"""
        user_result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is not None:
            user.learning_style_json = json.dumps(style.model_dump())
            await self.db.flush()
