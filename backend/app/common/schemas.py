"""通用Pydantic模型"""
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
