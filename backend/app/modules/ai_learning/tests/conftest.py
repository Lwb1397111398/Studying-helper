"""AI学习模块测试夹具"""

import pytest
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter


@pytest.fixture
def mock_llm():
    from app.modules.ai_learning.tests.mock_llm import MockLLMClient

    return MockLLMClient()


@pytest.fixture
def sample_unit():
    return KnowledgeUnit(
        id="unit-1",
        book_id="book-1",
        chapter_id="chapter-1",
        title="测试知识单元",
        content="这是一个关于数据结构的测试内容。数组是一种线性表，它用连续的存储空间存储相同类型的元素。",
        order_index=0,
        char_offset_start=0,
        char_offset_end=100,
    )


@pytest.fixture
def sample_chapters():
    return [
        Chapter(
            id="chapter-1",
            book_id="book-1",
            title="第1章 绪论",
            chapter_number=1,
            order_index=0,
        ),
        Chapter(
            id="chapter-2",
            book_id="book-1",
            title="第2章 基础",
            chapter_number=2,
            order_index=1,
        ),
    ]


@pytest.fixture
def sample_units():
    return [
        KnowledgeUnit(
            id=f"unit-{i}",
            book_id="book-1",
            chapter_id="chapter-1",
            title=f"单元{i}",
            content=f"这是第{i}个知识单元的内容。" * 20,
            order_index=i,
            char_offset_start=i * 200,
            char_offset_end=(i + 1) * 200,
        )
        for i in range(5)
    ]
