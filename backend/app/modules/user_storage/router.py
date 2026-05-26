"""用户与存储模块的REST端点"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import UserModel, MasteryRecordModel
from app.deps import get_user_service, get_book_service, get_record_service, get_file_storage, get_current_user
from app.modules.user_storage.services import UserService, BookService, LearningRecordService, FileStorage
from app.modules.user_storage.auth import create_token
from app.modules.user_storage.schemas import (
    UserCreate, UserUpdate, User, UserProfile,
    BookCreate, Book, BookStatusUpdate,
    LearningRecordCreate, LearningRecordComplete, LearningRecord,
    DailyStats,
)

router = APIRouter()


# ========== 认证端点 ==========

class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    user: User


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    登录/注册二合一：用户存在则登录，不存在则自动创建。
    返回 JWT token + 用户信息。
    """
    result = await db.execute(select(UserModel).where(UserModel.username == body.username))
    user = result.scalar_one_or_none()
    if user is None:
        svc = UserService(db)
        user = await svc.create_user(username=body.username)

    token = create_token(user.id)
    return LoginResponse(token=token, user=User.model_validate(user))


# ========== 用户端点 ==========

@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str, current_user: str = Depends(get_current_user),
                   svc: UserService = Depends(get_user_service)):
    """获取用户"""
    if current_user != "anonymous" and current_user != user_id:
        raise HTTPException(status_code=403, detail="无权查看其他用户信息")
    return await svc.get_user(user_id)


@router.put("/users/preferences", response_model=User)
async def update_preferences(body: UserUpdate, current_user: str = Depends(get_current_user),
                             svc: UserService = Depends(get_user_service)):
    """更新当前用户偏好（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    return await svc.update_preferences(
        current_user,
        daily_goal_minutes=body.daily_goal_minutes,
        preferred_language=body.preferred_language,
        learning_style_json=body.learning_style_json,
    )


@router.get("/users/profile", response_model=UserProfile)
async def get_profile(current_user: str = Depends(get_current_user),
                      svc: UserService = Depends(get_user_service)):
    """获取当前用户画像（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    profile = await svc.get_profile(current_user)
    return UserProfile(
        user=User.model_validate(profile["user"]),
        total_books=profile["total_books"],
        total_learning_minutes=profile["total_learning_minutes"],
        total_units_learned=profile["total_units_learned"],
        current_streak=profile["current_streak"],
    )


# ========== 书籍端点 ==========

@router.post("/books", response_model=Book, status_code=201)
async def upload_book(
    title: str = Form(...),
    author: Optional[str] = Form(None),
    file_type: str = Form(...),
    file_size_bytes: int = Form(...),
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    svc: BookService = Depends(get_book_service),
    storage: FileStorage = Depends(get_file_storage),
):
    """上传书籍（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    content = await file.read()
    file_path = await storage.store(current_user, file.filename or f"{uuid4()}.{file_type}", content)

    book = await svc.upload_book(
        user_id=current_user,
        title=title,
        file_path=file_path,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        author=author,
    )
    return book


@router.get("/books")
async def list_books(page: int = 1, page_size: int = 20,
                     current_user: str = Depends(get_current_user),
                     svc: BookService = Depends(get_book_service)):
    """列出当前用户的书籍（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    result = await svc.list_books(current_user, page=page, page_size=page_size)
    return {
        "items": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "file_type": b.file_type,
                "total_chapters": b.total_chapters,
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


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(book_id: str, svc: BookService = Depends(get_book_service)):
    """删除书籍（级联删除关联数据）"""
    await svc.delete_book(book_id)


@router.get("/books/{book_id}/chapters")
async def get_book_chapters(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取书籍章节列表"""
    from app.db.models import ChapterModel, KnowledgeUnitModel

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

    result = []
    for chapter in chapters:
        chapter_units = [u for u in units if u.chapter_id == chapter.id]
        result.append({
            "id": chapter.id,
            "book_id": chapter.book_id,
            "title": chapter.title,
            "order_num": chapter.order_index,
            "knowledge_units": [
                {
                    "id": u.id,
                    "book_id": u.book_id,
                    "chapter_id": u.chapter_id,
                    "title": u.title,
                    "content": u.content,
                    "summary": u.summary,
                    "difficulty_level": u.difficulty_level,
                    "concepts": u.concepts.split(",") if u.concepts else [],
                }
                for u in chapter_units
            ],
        })

    return result


@router.put("/books/{book_id}/status", response_model=Book)
async def update_book_status(book_id: str, body: BookStatusUpdate,
                             svc: BookService = Depends(get_book_service)):
    """更新书籍状态"""
    return await svc.update_status(
        book_id,
        parse_status=body.parse_status,
        split_status=body.split_status,
        learn_status=body.learn_status,
        total_chapters=body.total_chapters,
        total_units=body.total_units,
        learned_units=body.learned_units,
    )


# ========== 学习记录端点 ==========

@router.post("/records", response_model=LearningRecord, status_code=201)
async def create_record(body: LearningRecordCreate, svc: LearningRecordService = Depends(get_record_service)):
    """创建学习记录"""
    record = await svc.create_record(
        user_id=body.user_id,
        book_id=body.book_id,
        session_id=body.session_id,
    )
    return record


@router.put("/records/{record_id}/complete", response_model=LearningRecord)
async def complete_record(record_id: str, body: LearningRecordComplete,
                          svc: LearningRecordService = Depends(get_record_service)):
    """完成学习记录"""
    return await svc.complete_record(
        record_id,
        duration_minutes=body.duration_minutes,
        units_covered=body.units_covered,
        questions_asked=body.questions_asked,
        test_score=body.test_score,
        annotations_created=body.annotations_created,
    )


# ========== 统计端点 ==========

@router.get("/stats/daily/{date}", response_model=Optional[DailyStats])
async def get_daily_stats(date: str,
                          current_user: str = Depends(get_current_user),
                          svc: LearningRecordService = Depends(get_record_service)):
    """获取当前用户每日统计（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    stats = await svc.get_daily_stats(current_user, date)
    if stats is None:
        return DailyStats(user_id=current_user, date=date)
    return stats


@router.get("/stats/streak")
async def get_streak(current_user: str = Depends(get_current_user),
                     svc: LearningRecordService = Depends(get_record_service)):
    """获取当前用户连续学习天数（需登录）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    streak = await svc.get_streak(current_user)
    return {"user_id": current_user, "streak": streak}


@router.get("/books/{book_id}/mastery")
async def get_book_mastery(book_id: str, current_user: str = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """获取书籍的掌握度记录"""
    result = await db.execute(
        select(MasteryRecordModel)
        .where(MasteryRecordModel.user_id == current_user)
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
