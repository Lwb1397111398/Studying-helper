"""用户与存储模块的REST端点"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import MasteryRecordModel
from app.deps import get_user_service, get_book_service
from app.modules.user_storage.services import UserService, BookService
from app.modules.user_storage.schemas import (
    UserUpdate, User, UserProfile,
    Book, BookInfoUpdate, BookMotivationUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["user_storage"])


def _safe_json_list(raw: str | None) -> list:
    """安全解析 JSON 字符串为列表，失败返回空列表"""
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ========== 用户端点 ==========

@router.get("/users/profile", response_model=UserProfile)
async def get_profile(svc: UserService = Depends(get_user_service)):
    """获取当前用户画像"""
    profile = await svc.get_profile("anonymous")
    return UserProfile(
        user=User.model_validate(profile["user"]),
        total_books=profile["total_books"],
        total_learning_minutes=profile["total_learning_minutes"],
        total_units_learned=profile["total_units_learned"],
        current_streak=profile["current_streak"],
    )


@router.put("/users/preferences", response_model=User)
async def update_preferences(body: UserUpdate,
                             svc: UserService = Depends(get_user_service)):
    """更新当前用户偏好"""
    return await svc.update_preferences(
        "anonymous",
        daily_goal_minutes=body.daily_goal_minutes,
        preferred_language=body.preferred_language,
        learning_style_json=body.learning_style_json,
    )


# ========== 书籍端点 ==========

@router.get("/books")
async def list_books(page: int = 1, page_size: int = 20,
                     svc: BookService = Depends(get_book_service)):
    """列出当前用户的书籍"""
    result = await svc.list_books("anonymous", page=page, page_size=page_size)
    return {
        "items": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "file_type": b.file_type,
                "total_chapters": b.total_chapters,
                "total_units": b.total_units,
                "learned_units": b.learned_units,
                "parse_status": b.parse_status,
                "split_status": b.split_status,
                "learn_status": b.learn_status,
                "reading_motivation": b.reading_motivation,
                "created_at": b.created_at,
            }
            for b in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "has_next": result["has_next"],
    }


@router.get("/books/{book_id}", response_model=Book)
async def get_book(book_id: str, svc: BookService = Depends(get_book_service)):
    """获取书籍详情"""
    return await svc.get_book(book_id)


@router.put("/books/{book_id}", response_model=Book)
async def update_book_info(book_id: str, body: BookInfoUpdate,
                           svc: BookService = Depends(get_book_service)):
    """更新书籍基本信息（标题/作者）"""
    return await svc.update_info(book_id, title=body.title, author=body.author)


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(book_id: str, svc: BookService = Depends(get_book_service)):
    """删除书籍（级联删除关联数据）"""
    import os
    file_path = await svc.delete_book(book_id)
    # commit 由 get_db() 统一管理
    # 物理文件删除在 commit 后执行（失败只打 warning）
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning(f"文件删除失败: {file_path}, 原因: {e}")


@router.get("/books/{book_id}/chapters")
async def get_book_chapters(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取书籍章节列表（支持多级层级）"""
    from app.db.models import ChapterModel, KnowledgeUnitModel, BookModel

    # 检查书籍是否存在
    book_result = await db.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    if book_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"书籍 {book_id} 不存在")

    chapters_result = await db.execute(
        select(ChapterModel)
        .where(ChapterModel.book_id == book_id)
        .order_by(ChapterModel.order_index)
    )
    chapters = list(chapters_result.scalars().all())

    units_result = await db.execute(
        select(KnowledgeUnitModel)
        .where(KnowledgeUnitModel.book_id == book_id)
        .order_by(KnowledgeUnitModel.order_index)
    )
    units = list(units_result.scalars().all())

    # 按 chapter_id 分组知识单元
    units_by_chapter = {}
    for u in units:
        if u.chapter_id not in units_by_chapter:
            units_by_chapter[u.chapter_id] = []
        units_by_chapter[u.chapter_id].append({
            "id": u.id,
            "book_id": u.book_id,
            "chapter_id": u.chapter_id,
            "title": u.title,
            "content": u.content,
            "summary": u.summary,
            "explanation": u.explanation or "",
            "difficulty_level": u.difficulty_level,
            "importance_score": u.importance_score if u.importance_score is not None else 0.5,
            "key_points": _safe_json_list(u.key_points),
            "concepts": _safe_json_list(u.concepts),
        })

    # 计算哪些章节是容器节点（有子节点）
    parent_ids = {ch.parent_id for ch in chapters if ch.parent_id}

    # 构建响应，包含 level 和 parent_id 用于前端构建树形结构
    result = []
    for chapter in chapters:
        result.append({
            "id": chapter.id,
            "book_id": chapter.book_id,
            "title": chapter.title,
            "level": chapter.level,
            "parent_id": chapter.parent_id,
            "order_index": chapter.order_index,
            "is_container": chapter.id in parent_ids,
            "knowledge_units": units_by_chapter.get(chapter.id, []),
        })

    return result


@router.put("/books/{book_id}/motivation", response_model=Book)
async def update_book_motivation(book_id: str, body: BookMotivationUpdate,
                                 svc: BookService = Depends(get_book_service)):
    """更新阅读动机"""
    return await svc.update_status(book_id, reading_motivation=body.reading_motivation)


@router.get("/books/{book_id}/mastery")
async def get_book_mastery(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取书籍的掌握度记录"""
    result = await db.execute(
        select(MasteryRecordModel)
        .where(MasteryRecordModel.user_id == "anonymous", MasteryRecordModel.book_id == book_id)
    )
    records = list(result.scalars().all())

    return [
        {
            "id": r.id,
            "knowledge_unit_id": r.knowledge_unit_id,
            "mastery_score": r.mastery_score,
            "mastery_level": r.mastery_level,
            "next_review_at": r.next_review_at,
            "review_count": r.review_count,
        }
        for r in records
    ]
