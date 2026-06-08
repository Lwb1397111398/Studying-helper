"""用户身份测试（单机模式）"""
import pytest

from app.modules.user_storage.auth import get_current_user_id


@pytest.mark.asyncio
async def test_get_current_user_id():
    """单机模式下固定返回 anonymous"""
    result = await get_current_user_id()
    assert result == "anonymous"
