"""学习方案路由测试"""

from types import SimpleNamespace

import pytest

from app.modules.learning_plan import router as plan_router
from app.modules.learning_plan.router import GeneratePlanRequest, generate_plan


class _FakePlanService:
    def __init__(self):
        self.generated_user_id = None

    async def load_units_from_db(self, db, book_id: str):
        return [SimpleNamespace(unit_id="unit-1")]

    async def generate_plan(self, user_id: str, book_id: str, units, daily_goal_minutes: int = 30):
        self.generated_user_id = user_id
        return SimpleNamespace(model_dump=lambda: {"user_id": user_id, "book_id": book_id})


@pytest.mark.asyncio
async def test_generate_plan_uses_current_user(monkeypatch):
    """生成学习方案应使用当前用户，而不是硬编码 anonymous。"""
    fake_service = _FakePlanService()
    monkeypatch.setattr(plan_router, "_get_service", lambda db: fake_service)

    result = await generate_plan(
        "book-1",
        GeneratePlanRequest(daily_goal_minutes=25),
        db=object(),
        current_user="user-123",
    )

    assert result == {"user_id": "user-123", "book_id": "book-1"}
    assert fake_service.generated_user_id == "user-123"
