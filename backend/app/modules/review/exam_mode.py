"""考前模式 - 生成考试和评估结果"""

import random
from typing import List, Dict, Optional
from datetime import datetime
from uuid import uuid4

from app.modules.review.schemas import (
    ReviewSession, ReviewQuestion, ExamConfig, ExamResult, MasteryRecord,
)
from app.modules.review.helpers import check_answer
from app.modules.knowledge_splitter.schemas import KnowledgeUnit


def create_exam_session(
    user_id: str,
    book_id: str,
    chapter_ids: List[str],
    config: ExamConfig,
    knowledge_units: List[KnowledgeUnit],
    mastery_records: List[MasteryRecord],
    confused_unit_ids: Optional[List[str]] = None,
) -> ReviewSession:
    """
    创建考前模式的复习会话。

    策略：
    1. 筛选薄弱知识点（掌握度 < 0.7 或有"不懂"标记）
    2. 按难度分布生成题目

    参数:
        user_id: 用户ID
        book_id: 书籍ID
        chapter_ids: 章节ID列表
        config: 考试配置
        knowledge_units: 知识单元列表
        mastery_records: 掌握度记录列表
        confused_unit_ids: 有"不懂"标记的单元ID列表

    返回:
        ReviewSession
    """
    confused_set = set(confused_unit_ids or [])

    # 构建掌握度映射
    mastery_map: Dict[str, MasteryRecord] = {
        r.knowledge_unit_id: r for r in mastery_records
    }

    # 筛选目标章节的单元
    chapter_set = set(chapter_ids)
    chapter_units = [
        u for u in knowledge_units
        if u.chapter_id in chapter_set
    ]

    if not chapter_units:
        return ReviewSession(
            user_id=user_id,
            book_id=book_id,
            review_type='exam',
            questions=[],
        )

    # 筛选薄弱知识点
    if config.focus_on_weak:
        weak_units = []
        for unit in chapter_units:
            mastery = mastery_map.get(unit.id)
            if mastery and mastery.mastery_score < 0.7:
                weak_units.append(unit)
            elif unit.id in confused_set:
                weak_units.append(unit)
        # 如果薄弱知识点不够，补充其他单元
        if len(weak_units) < config.question_count:
            other_units = [u for u in chapter_units if u not in weak_units]
            weak_units.extend(other_units)
        candidate_units = weak_units
    else:
        candidate_units = chapter_units

    # 按难度分类
    easy_units = [u for u in candidate_units if u.difficulty_level and u.difficulty_level <= 2]
    medium_units = [u for u in candidate_units if u.difficulty_level and u.difficulty_level == 3]
    hard_units = [u for u in candidate_units if u.difficulty_level and u.difficulty_level >= 4]
    # 无难度标记的归入中等
    no_difficulty = [u for u in candidate_units if not u.difficulty_level]
    medium_units.extend(no_difficulty)

    # 按配置分布计算各难度题目数
    total = config.question_count
    easy_count = round(total * config.difficulty_distribution.get('easy', 0.3))
    medium_count = round(total * config.difficulty_distribution.get('medium', 0.5))
    hard_count = total - easy_count - medium_count

    # 从各难度池中随机选取
    selected_units = []
    selected_units.extend(_random_select(easy_units, easy_count))
    selected_units.extend(_random_select(medium_units, medium_count))
    selected_units.extend(_random_select(hard_units, hard_count))

    # 如果不够，从剩余中补充
    if len(selected_units) < total:
        remaining = [u for u in candidate_units if u not in selected_units]
        selected_units.extend(_random_select(remaining, total - len(selected_units)))

    # 生成复习题
    questions = []
    for unit in selected_units:
        question = _generate_question(unit)
        questions.append(question)

    return ReviewSession(
        user_id=user_id,
        book_id=book_id,
        review_type='exam',
        questions=questions,
    )


def evaluate_exam(
    session: ReviewSession,
    answers: Dict[str, str],
) -> ExamResult:
    """
    评估考试结果。

    参数:
        session: 复习会话
        answers: 答案映射 {question_id: user_answer}

    返回:
        ExamResult
    """
    correct_count = 0
    total_count = len(session.questions)
    weak_points = []
    weak_unit_ids = set()

    for question in session.questions:
        user_answer = answers.get(question.id, "")
        question.user_answer = user_answer
        question.answered_at = datetime.now()

        # 判断正确性
        is_correct = check_answer(question.correct_answer, user_answer)
        question.is_correct = is_correct

        if is_correct:
            correct_count += 1
        else:
            weak_points.append(question.question)
            weak_unit_ids.add(question.unit_id)

    # 计算分数
    score = (correct_count / total_count * 100) if total_count > 0 else 0.0

    # 计算用时
    if session.ended_at:
        time_spent = (session.ended_at - session.started_at).total_seconds() / 60
    else:
        time_spent = 0.0

    return ExamResult(
        session_id=session.id,
        score=round(score, 2),
        passed=score >= 70.0,
        correct_count=correct_count,
        total_count=total_count,
        weak_points=weak_points,
        time_spent_minutes=round(time_spent, 1),
        recommended_review=list(weak_unit_ids),
    )


def _random_select(items: list, count: int) -> list:
    """从列表中随机选取指定数量的元素"""
    if count <= 0:
        return []
    if len(items) <= count:
        return list(items)
    return random.sample(items, count)


def _generate_question(unit: KnowledgeUnit) -> ReviewQuestion:
    """根据知识单元生成复习题"""
    # 使用标题和内容生成问题
    if unit.key_points:
        # 如果有要点，生成关于要点的问题
        question_text = f"请解释以下概念：{unit.title}"
        correct_answer = "; ".join(unit.key_points[:3])
    elif unit.summary:
        question_text = f"请简述：{unit.title}"
        correct_answer = unit.summary[:200]
    else:
        question_text = f"请描述：{unit.title}"
        correct_answer = unit.content[:200]

    return ReviewQuestion(
        unit_id=unit.id,
        question=question_text,
        question_type='short_answer',
        correct_answer=correct_answer,
    )
