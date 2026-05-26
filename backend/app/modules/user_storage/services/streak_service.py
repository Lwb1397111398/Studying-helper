"""连续天数计算服务（独立模块，消除循环依赖）"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStatsModel


class StreakService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_streak(self, user_id: str) -> int:
        """
        从最新日期往前扫，遇到 total_minutes == 0 立即停。
        不用查全年数据。
        """
        result = await self.db.execute(
            select(DailyStatsModel.date, DailyStatsModel.total_minutes)
            .where(
                DailyStatsModel.user_id == user_id,
                DailyStatsModel.total_minutes > 0,
            )
            .order_by(DailyStatsModel.date.desc())
        )
        rows = result.all()
        if not rows:
            return 0

        from app.common.time_utils import utc_now
        from datetime import timedelta

        streak = 0
        expected_date = utc_now().date()

        for row_date, row_minutes in rows:
            row_date_str = row_date  # 已经是 date 或 str
            if isinstance(row_date_str, str):
                from datetime import datetime as dt
                row_date_obj = dt.strptime(row_date_str, "%Y-%m-%d").date()
            else:
                row_date_obj = row_date_str

            if row_date_obj == expected_date:
                streak += 1
                expected_date -= timedelta(days=1)
            elif row_date_obj < expected_date:
                # 断档了
                break
            # row_date_obj > expected_date 不可能发生（已按 desc 排序）

        return streak
