"""缓存服务"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time_utils import utc_now
from app.db.models import CacheEntryModel


class CacheService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str) -> str | None:
        result = await self.db.execute(select(CacheEntryModel).where(CacheEntryModel.key == key))
        entry = result.scalar_one_or_none()
        if entry is None:
            return None
        expires_at = entry.expires_at
        # SQLite 可能返回 offset-naive datetime，统一转成 offset-aware 再比较
        if expires_at.tzinfo is None:
            from datetime import timezone as tz
            expires_at = expires_at.replace(tzinfo=tz.utc)
        if expires_at < utc_now():
            await self.db.delete(entry)
            await self.db.flush()
            return None
        entry.access_count += 1
        await self.db.flush()
        return entry.value

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        now = utc_now()
        expires = now + timedelta(seconds=ttl_seconds)

        result = await self.db.execute(select(CacheEntryModel).where(CacheEntryModel.key == key))
        entry = result.scalar_one_or_none()
        if entry:
            entry.value = value
            entry.created_at = now
            entry.expires_at = expires
            entry.access_count = 0
        else:
            entry = CacheEntryModel(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires,
            )
            self.db.add(entry)
        await self.db.flush()

    async def delete(self, key: str) -> bool:
        result = await self.db.execute(select(CacheEntryModel).where(CacheEntryModel.key == key))
        entry = result.scalar_one_or_none()
        if entry:
            await self.db.delete(entry)
            await self.db.flush()
            return True
        return False

    async def invalidate_pattern(self, pattern: str) -> int:
        like_pattern = pattern.replace("*", "%")
        result = await self.db.execute(
            select(CacheEntryModel).where(CacheEntryModel.key.like(like_pattern))
        )
        entries = list(result.scalars().all())
        for entry in entries:
            await self.db.delete(entry)
        await self.db.flush()
        return len(entries)

    async def evict_expired(self) -> int:
        now = utc_now()
        result = await self.db.execute(
            select(CacheEntryModel).where(CacheEntryModel.expires_at < now)
        )
        entries = list(result.scalars().all())
        for entry in entries:
            await self.db.delete(entry)
        await self.db.flush()
        return len(entries)
