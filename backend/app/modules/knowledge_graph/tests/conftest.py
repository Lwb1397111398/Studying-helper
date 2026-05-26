"""知识图谱模块测试夹具"""

import pytest


@pytest.fixture
def sample_units():
    """示例知识单元列表"""
    return [
        {
            "id": "unit-1",
            "book_id": "book-1",
            "chapter_id": "chapter-1",
            "title": "数组基础",
            "content": "数组是一种线性表，用连续的存储空间存储相同类型的元素。",
            "summary": "数组是基本的数据结构，支持随机访问。",
            "concepts": ["数组", "线性表", "随机访问"],
            "difficulty_level": 2,
            "importance_score": 0.8,
        },
        {
            "id": "unit-2",
            "book_id": "book-1",
            "chapter_id": "chapter-1",
            "title": "链表结构",
            "content": "链表是一种物理存储单元上非连续的线性表。",
            "summary": "链表通过指针连接节点，支持动态大小。",
            "concepts": ["链表", "线性表", "指针"],
            "difficulty_level": 3,
            "importance_score": 0.7,
            "prerequisites": ["数组基础"],
        },
        {
            "id": "unit-3",
            "book_id": "book-1",
            "chapter_id": "chapter-2",
            "title": "二叉树遍历",
            "content": "二叉树的遍历包括前序、中序、后序和层序遍历。",
            "summary": "二叉树遍历是树结构的基本操作。",
            "concepts": ["二叉树", "遍历", "前序", "中序"],
            "difficulty_level": 4,
            "importance_score": 0.9,
            "prerequisites": ["链表结构"],
        },
    ]


@pytest.fixture
def sample_chapters():
    """示例章节列表"""
    return [
        {"id": "chapter-1", "title": "基础数据结构", "chapter_number": 1},
        {"id": "chapter-2", "title": "树与图", "chapter_number": 2},
    ]


@pytest.fixture
def sample_mastery_records():
    """示例掌握度记录"""
    return [
        {
            "id": "mr-1",
            "knowledge_unit_id": "unit-1",
            "mastery_score": 0.8,
            "mastery_level": "proficient",
        },
        {
            "id": "mr-2",
            "knowledge_unit_id": "unit-2",
            "mastery_score": 0.3,
            "mastery_level": "beginner",
        },
    ]


@pytest.fixture
def sample_graph(sample_units, sample_chapters):
    """示例知识图谱（通过构建器生成）"""
    from app.modules.knowledge_graph.graph_builder import GraphBuilder
    builder = GraphBuilder()
    return builder.build_from_data("book-1", sample_units, sample_chapters)
