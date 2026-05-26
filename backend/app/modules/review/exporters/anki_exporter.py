"""Anki卡片导出器"""

from typing import List, Dict
from datetime import datetime

from app.modules.review.schemas import ExportResult, ExportFormat


def export_anki(
    book_title: str,
    knowledge_units: List[Dict],
    mastery_records: Dict[str, Dict],
) -> ExportResult:
    """
    导出Anki TSV格式的闪卡。

    格式：问题\\t答案\\t标签

    参数:
        book_title: 书名
        knowledge_units: 知识单元列表 [{id, title, summary, key_points, chapter_id}]
        mastery_records: 掌握度映射 {unit_id: {score, level}}

    返回:
        ExportResult
    """
    lines = []
    # Anki TSV不支持表头，直接导出卡片

    for unit in knowledge_units:
        unit_id = unit.get('id', '')
        title = unit.get('title', '未命名')
        summary = unit.get('summary', '')
        key_points = unit.get('key_points', [])

        # 标签：书名 + 掌握度等级
        tags = [book_title.replace(' ', '_')]
        mastery = mastery_records.get(unit_id)
        if mastery:
            tags.append(mastery.get('level', 'unknown'))

        tag_str = ' '.join(tags)

        # 卡片1：标题 -> 摘要
        if summary:
            question = f"请解释：{title}"
            answer = summary.replace('\t', ' ').replace('\n', ' ')
            lines.append(f"{question}\t{answer}\t{tag_str}")

        # 卡片2：针对每个要点
        for i, point in enumerate(key_points):
            question = f"关于「{title}」的要点{i + 1}是什么？"
            answer = point.replace('\t', ' ').replace('\n', ' ')
            lines.append(f"{question}\t{answer}\t{tag_str}")

    content = "\n".join(lines)
    filename = f"{book_title}_Anki卡片.tsv"

    return ExportResult(
        format=ExportFormat.ANKI,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )
