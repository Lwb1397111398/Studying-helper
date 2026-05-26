"""教学引擎模块"""

from app.modules.teaching.schemas import (
    TeachingPhase,
    TeachingStrategy,
    KnowledgeType,
    CognitiveLevel,
    UserTeachingProfile,
    TeachingMessage,
    UserQuestion,
    Annotation,
    SessionTest,
    TeachingSession,
    SessionSummary,
)

from app.modules.teaching.service import TeachingService
from app.modules.teaching.strategies import select_teaching_strategy

__all__ = [
    "TeachingPhase",
    "TeachingStrategy",
    "KnowledgeType",
    "CognitiveLevel",
    "UserTeachingProfile",
    "TeachingMessage",
    "UserQuestion",
    "Annotation",
    "SessionTest",
    "TeachingSession",
    "SessionSummary",
    "TeachingService",
    "select_teaching_strategy",
]
