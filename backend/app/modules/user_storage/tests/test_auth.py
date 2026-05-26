"""JWT 认证测试"""
import pytest
from datetime import timedelta, timezone, datetime

from app.modules.user_storage.auth import create_token, decode_token, get_current_user_id
from app.config import settings


def test_create_and_decode_token():
    """创建 token 后能正确解码出 user_id"""
    user_id = "test-user-123"
    token = create_token(user_id)
    assert isinstance(token, str)
    decoded = decode_token(token)
    assert decoded == user_id


def test_token_expired():
    """过期 token 应抛 401"""
    import jwt
    from fastapi import HTTPException

    # 手动创建一个已过期的 token
    payload = {
        "sub": "user1",
        "iat": datetime.now(timezone.utc) - timedelta(hours=100),
        "exp": datetime.now(timezone.utc) - timedelta(hours=99),
        "jti": "fake-jti",
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        decode_token(expired_token)
    assert exc_info.value.status_code == 401
    assert "过期" in exc_info.value.detail


def test_token_invalid():
    """伪造 token 应抛 401"""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        decode_token("this.is.fake")
    assert exc_info.value.status_code == 401


def test_token_tampered():
    """篡改 token 应抛 401"""
    import jwt
    from fastapi import HTTPException

    # 用错误 secret 签名
    bad_token = jwt.encode({"sub": "user1"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        decode_token(bad_token)
    assert exc_info.value.status_code == 401
