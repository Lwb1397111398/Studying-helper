"""Markdown笔记导出器"""

from typing import List, Dict
from datetime import datetime, timezone

from app.modules.review.schemas import ExportResult, ExportFormat


def export_markdown(
    book_title: str,
    chapters: List[Dict],
    knowledge_units: List[Dict],
    mastery_records: Dict[str, Dict],
) -> ExportResult:
    """
    导出Markdown格式的复习笔记。

    参数:
        book_title: 书名
        chapters: 章节列表 [{id, title, chapter_number}]
        knowledge_units: 知识单元列表 [{id, chapter_id, title, summary, key_points}]
        mastery_records: 掌握度映射 {unit_id: {score, level}}

    返回:
        ExportResult
    """
    lines = []
    lines.append(f"# {book_title} - 复习笔记")
    lines.append(f"\n导出时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n")

    # 按章节组织
    chapter_map = {c['id']: c for c in chapters}
    units_by_chapter: Dict[str, list] = {}
    for unit in knowledge_units:
        cid = unit.get('chapter_id', '')
        if cid not in units_by_chapter:
            units_by_chapter[cid] = []
        units_by_chapter[cid].append(unit)

    for chapter in sorted(chapters, key=lambda c: c.get('chapter_number', 0)):
        lines.append(f"\n## 第{chapter.get('chapter_number', '?')}章 {chapter['title']}\n")

        chapter_units = units_by_chapter.get(chapter['id'], [])
        for unit in chapter_units:
            lines.append(f"### {unit.get('title', '未命名')}\n")

            # 掌握度标记
            mastery = mastery_records.get(unit.get('id', ''))
            if mastery:
                level_emoji = {
                    'mastered': '[已掌握]',
                    'proficient': '[熟练]',
                    'familiar': '[熟悉]',
                    'beginner': '[初学]',
                }
                level = mastery.get('mastery_level', mastery.get('level', ''))
                score = mastery.get('mastery_score', mastery.get('score', 0))
                level_text = level_emoji.get(level, '[未知]')
                lines.append(f"掌握度：{level_text} ({score:.0%})\n")

            # 摘要
            summary = unit.get('summary', '')
            if summary:
                lines.append(f"**摘要：** {summary}\n")

            # 要点
            key_points = unit.get('key_points', [])
            if key_points:
                lines.append("**要点：**\n")
                for point in key_points:
                    lines.append(f"- {point}")
                lines.append("")

    content = "\n".join(lines)
    filename = f"{book_title}_复习笔记.md"

    return ExportResult(
        format=ExportFormat.MARKDOWN,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )
