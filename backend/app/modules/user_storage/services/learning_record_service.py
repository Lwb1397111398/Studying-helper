"""学习记录服务"""
import json
from datetime import timedelta
from typing import List
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.time_utils import utc_now, date_str
from app.db.models import LearningRecordModel, DailyStatsModel


class LearningRecordService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(self, user_id: str, book_id: str, session_id: str) -> LearningRecordModel:
        record = LearningRecordModel(
            id=str(uuid4()),
            user_id=user_id,
            book_id=book_id,
            session_id=session_id,
            started_at=utc_now(),
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def complete_record(self, record_id: str, duration_minutes: int | None = None,
                              units_covered: list | None = None, questions_asked: int = 0,
                              test_score: float | None = None, annotations_created: int = 0) -> LearningRecordModel:
        result = await self.db.execute(select(LearningRecordModel).where(LearningRecordModel.id == record_id))
        record = result.scalar_one_or_none()
        if record is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"学习记录 {record_id} 不存在")

        record.ended_at = utc_now()
        record.duration_minutes = duration_minutes
        record.units_covered = json.dumps(units_covered) if units_covered else None
        record.questions_asked = questions_asked
        record.test_score = test_score
        record.annotations_created = annotations_created

        await self._update_daily_stats(
            record.user_id,
            duration_minutes or 0,
            len(units_covered) if units_covered else 0,
            test_score,
        )
        await self.db.flush()
        return record

    async def _update_daily_stats(self, user_id: str, minutes: int, units_count: int,
                                  test_score: float | None) -> None:
        today = date_str()
        result = await self.db.execute(
            select(DailyStatsModel)
            .where(DailyStatsModel.user_id == user_id, DailyStatsModel.date == today)
        )
        stats = result.scalar_one_or_none()

        if stats is None:
            yesterday = date_str(utc_now() - timedelta(days=1))
            yesterday_result = await self.db.execute(
                select(DailyStatsModel.streak_day)
                .where(DailyStatsModel.user_id == user_id, DailyStatsModel.date == yesterday)
            )
            yesterday_streak = yesterday_result.scalar() or 0

            stats = DailyStatsModel(
                user_id=user_id,
                date=today,
                total_minutes=minutes,
                units_learned=units_count,
                tests_taken=1 if test_score is not None else 0,
                avg_test_score=test_score or 0,
                streak_day=yesterday_streak + 1 if minutes > 0 else 0,
            )
            self.db.add(stats)
        else:
            stats.total_minutes += minutes
            stats.units_learned += units_count
            if test_score is not None:
                old_total = stats.avg_test_score * stats.tests_taken
                stats.tests_taken += 1
                stats.avg_test_score = (old_total + test_score) / stats.tests_taken

    async def get_daily_stats(self, user_id: str, date: str) -> DailyStatsModel | None:
        result = await self.db.execute(
            select(DailyStatsModel)
            .where(DailyStatsModel.user_id == user_id, DailyStatsModel.date == date)
        )
        return result.scalar_one_or_none()

    async def get_streak(self, user_id: str) -> int:
        from app.modules.user_storage.services.streak_service import StreakService
        return await StreakService(self.db).calculate_streak(user_id)

    async def get_stats_range(self, user_id: str, start_date: str, end_date: str) -> List[DailyStatsModel]:
        result = await self.db.execute(
            select(DailyStatsModel)
            .where(
                DailyStatsModel.user_id == user_id,
                DailyStatsModel.date >= start_date,
                DailyStatsModel.date <= end_date,
            )
            .order_by(DailyStatsModel.date)
        )
        return list(result.scalars().all())
