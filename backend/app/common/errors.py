"""错误处理模块"""
from enum import Enum
from fastapi import HTTPException


class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATABASE_ERROR = "DATABASE_ERROR"


class ServiceError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details


# FastAPI exception handler状态码映射
ERROR_STATUS_MAP = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.PROCESSING_ERROR: 500,
    ErrorCode.EXTERNAL_API_ERROR: 502,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INSUFFICIENT_DATA: 422,
    ErrorCode.DATABASE_ERROR: 500,
}
