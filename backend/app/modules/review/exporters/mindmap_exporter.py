"""思维导图导出器 - 支持Mermaid和PlantUML格式"""

from typing import List, Dict
from datetime import datetime

from app.modules.review.schemas import ExportResult, ExportFormat


def export_mindmap_mermaid(
    book_title: str,
    chapters: List[Dict],
    knowledge_units: List[Dict],
    mastery_records: Dict[str, Dict],
) -> ExportResult:
    """
    导出Mermaid格式的思维导图。

    参数:
        book_title: 书名
        chapters: 章节列表 [{id, title, chapter_number}]
        knowledge_units: 知识单元列表 [{id, chapter_id, title, key_points}]
        mastery_records: 掌握度映射 {unit_id: {score, level}}

    返回:
        ExportResult
    """
    lines = ["mindmap"]
    lines.append(f"  root(({book_title}))")

    # 按章节组织
    units_by_chapter: Dict[str, list] = {}
    for unit in knowledge_units:
        cid = unit.get('chapter_id', '')
        if cid not in units_by_chapter:
            units_by_chapter[cid] = []
        units_by_chapter[cid].append(unit)

    for chapter in sorted(chapters, key=lambda c: c.get('chapter_number', 0)):
        chapter_title = chapter.get('title', '未命名章节')
        lines.append(f"    {chapter_title}")

        chapter_units = units_by_chapter.get(chapter['id'], [])
        for unit in chapter_units:
            unit_title = unit.get('title', '未命名').replace('"', "'")

            # 根据掌握度添加标记
            mastery = mastery_records.get(unit.get('id', ''))
            if mastery:
                level = mastery.get('level', '')
                if level == 'mastered':
                    prefix = "[ok]"
                elif level == 'proficient':
                    prefix = "[good]"
                elif level == 'familiar':
                    prefix = "[warn]"
                else:
                    prefix = "[!]"
            else:
                prefix = ""

            lines.append(f"      {prefix}{unit_title}")

            # 添加关键要点作为子节点
            key_points = unit.get('key_points', [])
            for point in key_points[:3]:  # 最多3个要点
                point_text = point.replace('"', "'")[:50]
                lines.append(f"        {point_text}")

    content = "\n".join(lines)
    filename = f"{book_title}_思维导图.mmd"

    return ExportResult(
        format=ExportFormat.MIND_MAP_MERMAID,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )


def export_mindmap_plantuml(
    book_title: str,
    chapters: List[Dict],
    knowledge_units: List[Dict],
    mastery_records: Dict[str, Dict],
) -> ExportResult:
    """
    导出PlantUML格式的思维导图。

    参数:
        book_title: 书名
        chapters: 章节列表 [{id, title, chapter_number}]
        knowledge_units: 知识单元列表 [{id, chapter_id, title, key_points}]
        mastery_records: 掌握度映射 {unit_id: {score, level}}

    返回:
        ExportResult
    """
    lines = ["@startmindmap"]
    lines.append(f"title {book_title}")
    lines.append("")

    # 颜色定义
    lines.append("* " + book_title)

    # 按章节组织
    units_by_chapter: Dict[str, list] = {}
    for unit in knowledge_units:
        cid = unit.get('chapter_id', '')
        if cid not in units_by_chapter:
            units_by_chapter[cid] = []
        units_by_chapter[cid].append(unit)

    for chapter in sorted(chapters, key=lambda c: c.get('chapter_number', 0)):
        chapter_title = chapter.get('title', '未命名章节')
        lines.append(f"** {chapter_title}")

        chapter_units = units_by_chapter.get(chapter['id'], [])
        for unit in chapter_units:
            unit_title = unit.get('title', '未命名')

            # 根据掌握度选择颜色
            mastery = mastery_records.get(unit.get('id', ''))
            if mastery:
                level = mastery.get('level', '')
                color_map = {
                    'mastered': '2ECC71',
                    'proficient': '3498DB',
                    'familiar': 'F39C12',
                    'beginner': 'E74C3C',
                }
                color = color_map.get(level, '95A5A6')
            else:
                color = '95A5A6'

            lines.append(f"***[{color}] {unit_title}")

            # 关键要点
            key_points = unit.get('key_points', [])
            for point in key_points[:3]:
                point_text = point[:50].replace('\n', ' ')
                lines.append(f"**** {point_text}")

    lines.append("")
    lines.append("@endmindmap")

    content = "\n".join(lines)
    filename = f"{book_title}_思维导图.puml"

    return ExportResult(
        format=ExportFormat.MIND_MAP_PLANTUML,
        content=content,
        filename=filename,
        size_bytes=len(content.encode('utf-8')),
    )
