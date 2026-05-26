"""导出功能测试"""

import pytest
from app.modules.review.exporters import (
    export_markdown, export_anki, export_wrong_answers,
    export_mindmap_mermaid, export_mindmap_plantuml,
)
from app.modules.review.schemas import ExportFormat


@pytest.fixture
def sample_data():
    """导出测试数据"""
    chapters = [
        {"id": "ch-1", "title": "基础", "chapter_number": 1},
        {"id": "ch-2", "title": "进阶", "chapter_number": 2},
    ]
    units = [
        {
            "id": "u-1", "chapter_id": "ch-1", "title": "数组",
            "summary": "数组是基本数据结构",
            "key_points": ["连续存储", "随机访问"],
        },
        {
            "id": "u-2", "chapter_id": "ch-1", "title": "链表",
            "summary": "链表是动态数据结构",
            "key_points": ["非连续存储", "指针连接"],
        },
        {
            "id": "u-3", "chapter_id": "ch-2", "title": "二叉树",
            "summary": "树结构",
            "key_points": ["递归遍历"],
        },
    ]
    mastery = {
        "u-1": {"score": 0.9, "level": "mastered"},
        "u-2": {"score": 0.5, "level": "familiar"},
    }
    return chapters, units, mastery


class TestMarkdownExporter:
    """测试Markdown导出"""

    def test_basic_export(self, sample_data):
        """基本导出"""
        chapters, units, mastery = sample_data
        result = export_markdown("测试书", chapters, units, mastery)
        assert result.format == ExportFormat.MARKDOWN
        assert "测试书" in result.content
        assert "数组" in result.content
        assert result.filename.endswith(".md")
        assert result.size_bytes > 0

    def test_contains_mastery_info(self, sample_data):
        """包含掌握度信息"""
        chapters, units, mastery = sample_data
        result = export_markdown("测试书", chapters, units, mastery)
        assert "已掌握" in result.content or "[已掌握]" in result.content

    def test_chapter_organization(self, sample_data):
        """按章节组织"""
        chapters, units, mastery = sample_data
        result = export_markdown("测试书", chapters, units, mastery)
        assert "第1章" in result.content
        assert "第2章" in result.content


class TestAnkiExporter:
    """测试Anki导出"""

    def test_basic_export(self, sample_data):
        """基本导出"""
        _, units, mastery = sample_data
        result = export_anki("测试书", units, mastery)
        assert result.format == ExportFormat.ANKI
        assert result.filename.endswith(".tsv")

    def test_tsv_format(self, sample_data):
        """TSV格式正确"""
        _, units, mastery = sample_data
        result = export_anki("测试书", units, mastery)
        lines = result.content.strip().split("\n")
        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 3  # 问题\t答案\t标签

    def test_cards_per_unit(self, sample_data):
        """每个单元生成卡片"""
        _, units, mastery = sample_data
        result = export_anki("测试书", units, mastery)
        # 每个有摘要的单元至少1张卡片
        lines = result.content.strip().split("\n")
        assert len(lines) >= len(units)


class TestWrongAnswersExporter:
    """测试错题集导出"""

    def test_basic_export(self):
        """基本导出"""
        wrong_questions = [
            {
                "question": "什么是数组？",
                "correct_answer": "连续存储",
                "user_answer": "链式存储",
                "unit_title": "数组基础",
                "explanation": "数组使用连续内存",
                "answered_at": "2024-01-01",
            },
        ]
        result = export_wrong_answers("测试书", wrong_questions)
        assert result.format == ExportFormat.WRONG_ANSWERS
        assert "错题集" in result.content
        assert "数组" in result.content

    def test_empty_export(self):
        """空错题导出"""
        result = export_wrong_answers("测试书", [])
        assert result.format == ExportFormat.WRONG_ANSWERS
        assert "0 道错题" in result.content

    def test_contains_all_fields(self):
        """包含所有字段"""
        wrong_questions = [
            {
                "question": "问题1",
                "correct_answer": "正确答案",
                "user_answer": "用户答案",
                "unit_title": "单元标题",
                "explanation": "解析",
                "answered_at": "2024-01-01",
            },
        ]
        result = export_wrong_answers("测试书", wrong_questions)
        assert "正确答案" in result.content
        assert "用户答案" in result.content
        assert "解析" in result.content


class TestMindmapExporter:
    """测试思维导图导出"""

    def test_mermaid_export(self, sample_data):
        """Mermaid格式导出"""
        chapters, units, mastery = sample_data
        result = export_mindmap_mermaid("测试书", chapters, units, mastery)
        assert result.format == ExportFormat.MIND_MAP_MERMAID
        assert "mindmap" in result.content
        assert "测试书" in result.content
        assert result.filename.endswith(".mmd")

    def test_plantuml_export(self, sample_data):
        """PlantUML格式导出"""
        chapters, units, mastery = sample_data
        result = export_mindmap_plantuml("测试书", chapters, units, mastery)
        assert result.format == ExportFormat.MIND_MAP_PLANTUML
        assert "@startmindmap" in result.content
        assert "@endmindmap" in result.content
        assert result.filename.endswith(".puml")

    def test_mermaid_contains_chapters(self, sample_data):
        """Mermaid包含章节"""
        chapters, units, mastery = sample_data
        result = export_mindmap_mermaid("测试书", chapters, units, mastery)
        assert "基础" in result.content
        assert "进阶" in result.content

    def test_plantuml_contains_units(self, sample_data):
        """PlantUML包含单元"""
        chapters, units, mastery = sample_data
        result = export_mindmap_plantuml("测试书", chapters, units, mastery)
        assert "数组" in result.content
        assert "链表" in result.content
