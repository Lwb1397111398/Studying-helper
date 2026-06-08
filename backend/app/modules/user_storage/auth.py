"""用户身份（单机模式，固定返回 anonymous）"""


async def get_current_user_id() -> str:
    """单机模式下固定返回 anonymous"""
    return "anonymous"
