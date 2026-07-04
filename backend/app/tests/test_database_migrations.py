"""数据库增量迁移测试"""

import sqlalchemy as sa
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.database import _run_migrations


@pytest.mark.asyncio
async def test_migrations_add_fsrs_columns_to_existing_mastery_records():
    """旧库的 mastery_records 表应补齐 FSRS 字段。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE TABLE knowledge_units (id TEXT PRIMARY KEY)"))
        await conn.execute(sa.text("CREATE TABLE annotations (id TEXT PRIMARY KEY)"))
        await conn.execute(sa.text("CREATE TABLE teaching_messages (id TEXT PRIMARY KEY)"))
        await conn.execute(sa.text("CREATE TABLE books (id TEXT PRIMARY KEY)"))
        await conn.execute(
            sa.text(
                """
                CREATE TABLE mastery_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    knowledge_unit_id TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    mastery_score FLOAT NOT NULL,
                    mastery_level TEXT NOT NULL,
                    next_review_at DATETIME NOT NULL
                )
                """
            )
        )

        await _run_migrations(conn)
        rows = (await conn.execute(sa.text("PRAGMA table_info(mastery_records)"))).all()

    await engine.dispose()

    columns = {row[1] for row in rows}
    assert {
        "stability",
        "difficulty",
        "lapses",
        "reps",
        "last_elapsed_days",
        "scheduled_days",
        "algorithm",
    }.issubset(columns)
