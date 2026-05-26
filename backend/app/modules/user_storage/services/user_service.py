"""用户服务"""
import json
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.time_utils import utc_now
from app.db.models import UserModel, BookModel, DailyStatsModel
from app.modules.user_storage.services.streak_service import StreakService
from app.modules.user_storage.schemas import LearningStyle


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, username: str, email: str | None = None,
                          daily_goal_minutes: int = 30, preferred_language: str = "zh") -> UserModel:
        now = utc_now()
        user = UserModel(
            id=str(uuid4()),
            username=username,
            email=email,
            daily_goal_minutes=daily_goal_minutes,
            preferred_language=preferred_language,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user(self, user_id: str) -> UserModel:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"用户 {user_id} 不存在")
        return user

    async def update_preferences(self, user_id: str, **kwargs) -> UserModel:
        user = await self.get_user(user_id)

        # 单独处理 learning_style_json：用 LearningStyle 校验
        style_json = kwargs.get("learning_style_json")
        if style_json is not None:
            try:
                style = LearningStyle.model_validate_json(style_json)
                kwargs["learning_style_json"] = style.model_dump_json()
            except Exception as e:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, f"learning_style 格式错误: {e}")

        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = utc_now()
        await self.db.flush()
        return user

    async def get_profile(self, user_id: str) -> dict:
        """获取用户画像（并行统计 + StreakService）"""
        import asyncio
        user = await self.get_user(user_id)

        book_count_coro = self.db.execute(
            select(func.count()).select_from(BookModel).where(BookModel.user_id == user_id)
        )
        total_minutes_coro = self.db.execute(
            select(func.coalesce(func.sum(DailyStatsModel.total_minutes), 0))
            .where(DailyStatsModel.user_id == user_id)
        )
        total_units_coro = self.db.execute(
            select(func.coalesce(func.sum(BookModel.learned_units), 0))
            .where(BookModel.user_id == user_id)
        )

        book_count, total_minutes_r, total_units_r = await asyncio.gather(
            book_count_coro, total_minutes_coro, total_units_coro
        )

        streak = await StreakService(self.db).calculate_streak(user_id)

        return {
            "user": user,
            "total_books": book_count.scalar() or 0,
            "total_learning_minutes": total_minutes_r.scalar() or 0,
            "total_units_learned": total_units_r.scalar() or 0,
            "current_streak": streak,
        }
