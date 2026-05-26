"""时间工具函数"""
from datetime import datetime, timezone, timedelta


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def date_str(dt: datetime | None = None) -> str:
    if dt is None:
        dt = utc_now()
    return dt.strftime("%Y-%m-%d")
