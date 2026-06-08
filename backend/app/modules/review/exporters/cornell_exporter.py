"""康奈尔笔记导出器"""

from typing import List, Dict, Optional
from datetime import datetime, timezone

from app.modules.review.schemas import ExportResult, ExportFormat


def export_cornell_notes(
    book_title: str,
    chapters: List[Dict],
    knowledge_units: List[Dict],
    annotations: Dict[str, Dict],
) -> ExportResult:
    """
    导出康奈尔笔记格式。

    参数:
        book_title: 书名
        chapters: 章节列表 [{id, title, chapter_number}]
        knowledge_units: 知识单元列表 [{id, chapter_id, title, summary, key_points}]
        annotations: 注释映射 {unit_id: {content, cornell_cues, cornell_summary}}

    返回:
        ExportResult
    """
    lines = []
    lines.append(f"# {book_title} - 康奈尔笔记")
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
            unit_id = unit.get('id', '')
            title = unit.get('title', '未命名')
            annotation = annotations.get(unit_id, {})

            lines.append(f"### {title}\n")

            # 康奈尔笔记三栏表格
            cues = annotation.get('cornell_cues', [])
            notes = annotation.get('content', '') or unit.get('summary', '')
            summary = annotation.get('cornell_summary', '')

            lines.append("| 线索栏 | 笔记栏 |")
            lines.append("|--------|--------|")

            # 格式化线索
            cues_text = ""
            if isinstance(cues, list):
                cues_text = "<br>".join(f"- {c}" for c in cues) if cues else "（未生成）"
            elif isinstance(cues, str):
                cues_text = cues if cues else "（未生成）"
            else:
                cues_text = "（未生成）"

            # 格式化笔记
            notes_text = notes if notes else "（无笔记）"

            lines.append(f"| {cues_text} | {notes_text} |")

            # 总结栏
            lines.append(f"\n**总结栏：** {summary if summary else '（未生成）'}\n")

            # 要点（补充信息）
            key_points = unit.get('key_points', [])
            if key_points:
                lines.append("**关键要点：**\n")
                for point in key_points:
                    lines.append(f"- {point}")
                lines.append("")

    content = "\n".join(lines)
    filename = f"{book_title}_康奈尔笔记.md"

    return ExportResult(
        format=ExportFormat.CORNELL_NOTES,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )
