"""错题集导出器"""

from typing import List, Dict
from datetime import datetime

from app.modules.review.schemas import ExportResult, ExportFormat


def export_wrong_answers(
    book_title: str,
    wrong_questions: List[Dict],
) -> ExportResult:
    """
    导出错题集。

    参数:
        book_title: 书名
        wrong_questions: 错题列表 [{
            question, correct_answer, user_answer,
            unit_title, explanation, answered_at
        }]

    返回:
        ExportResult
    """
    lines = []
    lines.append(f"# {book_title} - 错题集")
    lines.append(f"\n导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"共 {len(wrong_questions)} 道错题\n")
    lines.append("---\n")

    for i, q in enumerate(wrong_questions, 1):
        lines.append(f"## 错题 {i}")
        lines.append(f"\n**所属知识点：** {q.get('unit_title', '未知')}\n")
        lines.append(f"**题目：** {q.get('question', '')}\n")
        lines.append(f"**你的答案：** {q.get('user_answer', '未作答')}\n")
        lines.append(f"**正确答案：** {q.get('correct_answer', '')}\n")

        explanation = q.get('explanation', '')
        if explanation:
            lines.append(f"**解析：** {explanation}\n")

        answered_at = q.get('answered_at')
        if answered_at:
            lines.append(f"*作答时间：{answered_at}*\n")

        lines.append("---\n")

    content = "\n".join(lines)
    filename = f"{book_title}_错题集.md"

    return ExportResult(
        format=ExportFormat.WRONG_ANSWERS,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )
