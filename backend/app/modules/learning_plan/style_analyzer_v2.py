"""学习风格分析器 v2 - 连续值模型

改进：
1. 基于连续值的风格模型（替代布尔值）
2. 使用指数移动平均更新
3. 改进信息接收偏好估算
4. 添加置信度更新机制
"""

import json
import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LearningRecordModel, DailyStatsModel, UserModel


@dataclass
class ContinuousLearningStyle:
    """连续值学习风格模型"""

    # 学习节奏偏好 (0=慢速, 1=快速)
    pace_preference: float = 0.5

    # 内容偏好 (0=理论优先, 1=示例优先)
    example_affinity: float = 0.5

    # 交互偏好 (0=自主学习, 1=高度交互)
    interaction_preference: float = 0.5

    # 脚手架需求 (0=独立学习, 1=需要指导)
    scaffold_need: float = 0.5

    # 信息接收偏好 (基于实际行为数据)
    visual_weight: float = 0.25
    reading_weight: float = 0.25
    practice_weight: float = 0.25
    discussion_weight: float = 0.25

    # 学习时间偏好 (0=短时间高频, 1=长时间低频)
    session_duration_preference: float = 0.5

    # 难度偏好 (0=简单, 1=困难)
    difficulty_preference: float = 0.5

    # 置信度 (0-1)
    confidence: float = 0.0

    # 数据点数量
    data_points: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'pace_preference': self.pace_preference,
            'example_affinity': self.example_affinity,
            'interaction_preference': self.interaction_preference,
            'scaffold_need': self.scaffold_need,
            'visual_weight': self.visual_weight,
            'reading_weight': self.reading_weight,
            'practice_weight': self.practice_weight,
            'discussion_weight': self.discussion_weight,
            'session_duration_preference': self.session_duration_preference,
            'difficulty_preference': self.difficulty_preference,
            'confidence': self.confidence,
            'data_points': self.data_points,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContinuousLearningStyle':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionDataV2:
    """学习会话数据 v2"""
    # 基础数据
    duration_minutes: float = 0.0
    questions_asked: int = 0
    test_score: Optional[float] = None
    units_covered: int = 0

    # 表现数据
    accuracy: float = 0.5
    avg_response_time: float = 30.0
    confusion_count: int = 0

    # 交互数据
    content_types_viewed: Dict[str, int] = field(default_factory=dict)
    practice_count: int = 0
    review_count: int = 0

    # 难度数据
    avg_difficulty: float = 3.0
    difficulty_range: float = 1.0


class LearningStyleAnalyzerV2:
    """学习风格分析器 v2"""

    MIN_SESSIONS_FOR_ANALYSIS = 5
    ALPHA = 0.3  # 指数移动平均系数

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_style(self, user_id: str) -> ContinuousLearningStyle:
        """
        获取用户学习风格

        策略：
        - 有足够历史数据 -> 基于数据分析
        - 数据不足 -> 返回默认风格 + 低置信度
        """
        # 先查用户表中是否已有缓存的学习风格
        user_result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            return ContinuousLearningStyle()

        # 尝试加载 v2 风格
        if hasattr(user, 'learning_style_v2_json') and user.learning_style_v2_json:
            try:
                cached = json.loads(user.learning_style_v2_json)
                style = ContinuousLearningStyle.from_dict(cached)
                if style.confidence >= 0.3:
                    return style
            except (json.JSONDecodeError, ValueError):
                pass

        # 从历史记录分析
        record_count = await self._count_records(user_id)
        if record_count < self.MIN_SESSIONS_FOR_ANALYSIS:
            style = ContinuousLearningStyle(
                confidence=self._calculate_confidence(record_count)
            )
            return style

        style = await self._analyze_from_records(user_id)
        await self._save_style(user_id, style)
        return style

    async def update_from_session(self, user_id: str, session_data: SessionDataV2):
        """
        从学习会话数据更新学习风格

        使用指数移动平均更新各维度分数
        """
        current = await self.get_style(user_id)
        alpha = self.ALPHA

        # 1. 更新节奏偏好
        if session_data.duration_minutes > 0:
            # 短时间完成多内容 -> 快节奏
            pace_signal = min(1.0, session_data.units_covered / max(1, session_data.duration_minutes / 10))
            current.pace_preference = self._ema(current.pace_preference, pace_signal, alpha)

        # 2. 更新内容偏好
        if session_data.test_score is not None:
            # 高正确率 -> 偏好示例
            example_signal = session_data.test_score / 100.0
            current.example_affinity = self._ema(current.example_affinity, example_signal, alpha)

        # 3. 更新交互偏好
        if session_data.questions_asked > 0:
            # 提问多 -> 高交互偏好
            interaction_signal = min(1.0, session_data.questions_asked / 5.0)
            current.interaction_preference = self._ema(
                current.interaction_preference, interaction_signal, alpha
            )

        # 4. 更新脚手架需求
        if session_data.confusion_count > 0:
            # 困惑多 -> 需要更多指导
            scaffold_signal = min(1.0, session_data.confusion_count / 3.0)
            current.scaffold_need = self._ema(current.scaffold_need, scaffold_signal, alpha)
        elif session_data.accuracy > 0.8:
            # 表现好 -> 减少指导需求
            scaffold_signal = max(0.0, 1.0 - session_data.accuracy)
            current.scaffold_need = self._ema(current.scaffold_need, scaffold_signal, alpha)

        # 5. 更新信息接收偏好
        if session_data.content_types_viewed:
            total = sum(session_data.content_types_viewed.values())
            if total > 0:
                visual_signal = session_data.content_types_viewed.get("visual", 0) / total
                reading_signal = session_data.content_types_viewed.get("text", 0) / total
                practice_signal = session_data.content_types_viewed.get("practice", 0) / total
                discussion_signal = session_data.content_types_viewed.get("discussion", 0) / total

                current.visual_weight = self._ema(current.visual_weight, visual_signal, alpha)
                current.reading_weight = self._ema(current.reading_weight, reading_signal, alpha)
                current.practice_weight = self._ema(current.practice_weight, practice_signal, alpha)
                current.discussion_weight = self._ema(current.discussion_weight, discussion_signal, alpha)

                # 归一化
                total_weight = (current.visual_weight + current.reading_weight +
                               current.practice_weight + current.discussion_weight)
                if total_weight > 0:
                    current.visual_weight /= total_weight
                    current.reading_weight /= total_weight
                    current.practice_weight /= total_weight
                    current.discussion_weight /= total_weight

        # 6. 更新学习时间偏好
        if session_data.duration_minutes > 0:
            # 长时间学习 -> 偏好长时间会话
            duration_signal = min(1.0, session_data.duration_minutes / 60.0)
            current.session_duration_preference = self._ema(
                current.session_duration_preference, duration_signal, alpha
            )

        # 7. 更新难度偏好
        if session_data.avg_difficulty > 0:
            difficulty_signal = (session_data.avg_difficulty - 1) / 4  # 归一化到 0-1
            current.difficulty_preference = self._ema(
                current.difficulty_preference, difficulty_signal, alpha
            )

        # 更新置信度和数据点
        current.data_points += 1
        current.confidence = min(1.0, current.confidence + alpha * 0.1)

        await self._save_style(user_id, current)

    def _ema(self, current: float, new: float, alpha: float) -> float:
        """指数移动平均"""
        return alpha * new + (1 - alpha) * current

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

    async def _analyze_from_records(self, user_id: str) -> ContinuousLearningStyle:
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
            return ContinuousLearningStyle()

        total = len(records)

        # 计算平均值
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

        # 分析节奏偏好
        pace_preference = min(1.0, avg_duration / 60.0)  # 归一化

        # 分析内容偏好
        example_affinity = avg_score / 100.0 if avg_score > 0 else 0.5

        # 分析交互偏好
        interaction_preference = min(1.0, avg_questions / 5.0)

        # 分析脚手架需求（基于正确率和提问）
        scaffold_need = max(0.0, 1.0 - (avg_score / 100.0)) * 0.7 + min(1.0, avg_questions / 3.0) * 0.3

        # 分析信息接收偏好
        if stats:
            total_minutes = sum(s.total_minutes or 0 for s in stats)
            total_units = sum(s.units_learned or 0 for s in stats)
            total_reviews = sum(s.units_reviewed or 0 for s in stats)
            total_tests = sum(s.tests_taken or 0 for s in stats)

            denom = max(total_units + total_reviews + total_tests, 1)
            reading_weight = total_units / denom
            practice_weight = total_tests / denom
            visual_weight = total_reviews / denom
            discussion_weight = max(0.0, 1.0 - reading_weight - practice_weight - visual_weight)
        else:
            visual_weight = reading_weight = practice_weight = discussion_weight = 0.25

        # 分析学习时间偏好
        session_duration_preference = min(1.0, avg_duration / 60.0)

        # 分析难度偏好（基于测试分数的标准差）
        scores = [r.test_score for r in records if r.test_score is not None]
        if len(scores) >= 2:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            difficulty_preference = min(1.0, std_dev / 30.0)  # 标准差大 -> 喜欢挑战
        else:
            difficulty_preference = 0.5

        return ContinuousLearningStyle(
            pace_preference=round(pace_preference, 3),
            example_affinity=round(example_affinity, 3),
            interaction_preference=round(interaction_preference, 3),
            scaffold_need=round(scaffold_need, 3),
            visual_weight=round(visual_weight, 3),
            reading_weight=round(reading_weight, 3),
            practice_weight=round(practice_weight, 3),
            discussion_weight=round(discussion_weight, 3),
            session_duration_preference=round(session_duration_preference, 3),
            difficulty_preference=round(difficulty_preference, 3),
            confidence=self._calculate_confidence(total),
            data_points=total,
        )

    async def _save_style(self, user_id: str, style: ContinuousLearningStyle):
        """保存学习风格到用户表"""
        user_result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is not None:
            # 保存 v2 风格
            if hasattr(user, 'learning_style_v2_json'):
                user.learning_style_v2_json = json.dumps(style.to_dict())
            else:
                # 兼容旧版：保存到 learning_style_json
                user.learning_style_json = json.dumps(style.to_dict())
            await self.db.flush()

    def get_teaching_strategy_hint(self, style: ContinuousLearningStyle) -> Dict[str, Any]:
        """
        根据学习风格生成教学策略提示

        Returns:
            策略提示字典
        """
        return {
            'preferred_pace': 'fast' if style.pace_preference > 0.6 else 'slow' if style.pace_preference < 0.4 else 'normal',
            'preferred_scaffold': 'minimal' if style.scaffold_need < 0.4 else 'full' if style.scaffold_need > 0.6 else 'partial',
            'preferred_interaction': 'high' if style.interaction_preference > 0.6 else 'low' if style.interaction_preference < 0.4 else 'medium',
            'preferred_example': 'example_heavy' if style.example_affinity > 0.6 else 'theory_first' if style.example_affinity < 0.4 else 'balanced',
            'preferred_difficulty': 'challenging' if style.difficulty_preference > 0.6 else 'easy' if style.difficulty_preference < 0.4 else 'moderate',
            'dominant_modality': self._get_dominant_modality(style),
            'session_length': 'long' if style.session_duration_preference > 0.6 else 'short' if style.session_duration_preference < 0.4 else 'medium',
        }

    def _get_dominant_modality(self, style: ContinuousLearningStyle) -> str:
        """获取主导学习模态"""
        modalities = {
            'visual': style.visual_weight,
            'reading': style.reading_weight,
            'practice': style.practice_weight,
            'discussion': style.discussion_weight,
        }
        return max(modalities.items(), key=lambda x: x[1])[0]


def create_session_data_v2_from_dict(data: Dict[str, Any]) -> SessionDataV2:
    """从字典创建 SessionDataV2"""
    return SessionDataV2(
        duration_minutes=data.get('duration_minutes', 0.0),
        questions_asked=data.get('questions_asked', 0),
        test_score=data.get('test_score'),
        units_covered=data.get('units_covered', 0),
        accuracy=data.get('accuracy', 0.5),
        avg_response_time=data.get('avg_response_time', 30.0),
        confusion_count=data.get('confusion_count', 0),
        content_types_viewed=data.get('content_types_viewed', {}),
        practice_count=data.get('practice_count', 0),
        review_count=data.get('review_count', 0),
        avg_difficulty=data.get('avg_difficulty', 3.0),
        difficulty_range=data.get('difficulty_range', 1.0),
    )
