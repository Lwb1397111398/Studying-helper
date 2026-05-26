"""JWT 认证工具"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

security = HTTPBearer(auto_error=False)


def create_token(user_id: str) -> str:
    """签发 JWT，payload 含 user_id + jti（唯一标识）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> str:
    """验证 JWT，返回 user_id。失败抛 401。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    """
    从 Authorization header 提取 user_id。
    无 token 时返回 anonymous（向后兼容未登录场景）。
    """
    if credentials is None:
        return "anonymous"
    return decode_token(credentials.credentials)
