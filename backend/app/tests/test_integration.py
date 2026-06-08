"""集成测试 - 端到端流程验证"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata, TOCItem
from app.modules.knowledge_splitter.schemas import Chapter, KnowledgeUnit, SplitResult
from app.modules.knowledge_splitter.service import KnowledgeSplitterService
from app.modules.review.service import ReviewService
from app.modules.review.schemas import MasteryRecord, ReviewSession, ExamConfig
from app.modules.review.spaced_repetition import calculate_next_review, quality_from_correctness
from app.modules.knowledge_graph.service import KnowledgeGraphService
from app.modules.knowledge_graph.schemas import KnowledgeGraph, GraphQuery


@pytest_asyncio.fixture
async def db_session():
    """创建内存数据库"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sample_parsed_document():
    """示例解析文档"""
    return ParsedDocument(
        metadata=BookMetadata(
            title="Python编程入门",
            author="张三",
            file_type="txt",
            file_size_bytes=1024
        ),
        chapters=[
            Chapter(
                id="ch1",
                book_id="book1",
                title="第一章 Python基础",
                chapter_number=1,
                level=0,
                order_index=0
            ),
            Chapter(
                id="ch2",
                book_id="book1",
                title="第二章 数据类型",
                chapter_number=2,
                level=0,
                order_index=1
            )
        ],
        full_text="Python是一种解释型语言。数据类型包括整数、字符串等。",
        toc=[
            TOCItem(title="第一章 Python基础", level=0, char_offset=0),
            TOCItem(title="第二章 数据类型", level=0, char_offset=100)
        ]
    )


@pytest.fixture
def sample_knowledge_units():
    """示例知识单元"""
    return [
        KnowledgeUnit(
            id="unit1",
            book_id="book1",
            chapter_id="ch1",
            title="Python简介",
            content="Python是一种解释型、面向对象的编程语言。",
            order_index=0,
            char_offset_start=0,
            char_offset_end=50,
            summary="Python是解释型语言",
            difficulty_level=2,
            concepts=["Python", "解释型语言", "面向对象"]
        ),
        KnowledgeUnit(
            id="unit2",
            book_id="book1",
            chapter_id="ch2",
            title="数据类型",
            content="Python支持多种数据类型。",
            order_index=1,
            char_offset_start=50,
            char_offset_end=100,
            summary="Python数据类型",
            difficulty_level=3,
            concepts=["整数", "字符串", "列表"]
        )
    ]


@pytest.fixture
def sample_mastery_records():
    """示例掌握度记录"""
    now = datetime.now(timezone.utc)
    return [
        MasteryRecord(
            id="mastery1",
            user_id="user1",
            knowledge_unit_id="unit1",
            mastery_score=0.85,
            mastery_level="proficient",
            last_reviewed_at=now - timedelta(days=2),
            next_review_at=now - timedelta(days=1),  # 已到期
            review_count=3,
            ease_factor=2.5,
            interval_days=6
        ),
        MasteryRecord(
            id="mastery2",
            user_id="user1",
            knowledge_unit_id="unit2",
            mastery_score=0.45,
            mastery_level="familiar",
            last_reviewed_at=now - timedelta(days=5),
            next_review_at=now + timedelta(days=1),  # 未到期
            review_count=1,
            ease_factor=2.3,
            interval_days=1
        )
    ]


class TestKnowledgeSplitterIntegration:
    """知识拆分集成测试"""

    def test_split_document(self, sample_parsed_document):
        """测试文档拆分流程"""
        service = KnowledgeSplitterService()
        result = service.split(sample_parsed_document, "book1")

        assert isinstance(result, SplitResult)
        assert result.book_id == "book1"
        assert len(result.units) > 0
        assert result.split_stats.total_units > 0


class TestSpacedRepetitionIntegration:
    """间隔重复集成测试"""

    def test_spaced_repetition_flow(self):
        """测试间隔重复完整流程"""
        # 首次学习
        interval, ease, reps = calculate_next_review(4, 0, 2.5, 0)
        assert interval == 1

        # 第二次复习
        interval, ease, reps = calculate_next_review(4, 1, ease, interval)
        assert interval == 6

        # 第三次复习
        interval, ease, reps = calculate_next_review(4, 2, ease, interval)
        assert interval == round(6 * ease)

        # 失败重置
        interval, ease, reps = calculate_next_review(2, 3, ease, interval)
        assert interval == 1

    def test_quality_from_correctness(self):
        """测试质量分数计算"""
        # 正确 + 快速
        q = quality_from_correctness(True, 3.0, 10.0)
        assert q == 5

        # 正确 + 正常
        q = quality_from_correctness(True, 10.0, 10.0)
        assert q == 4

        # 错误
        q = quality_from_correctness(False, 5.0, 10.0)
        assert q < 3


class TestReviewIntegration:
    """复习引擎集成测试"""

    @pytest.mark.asyncio
    async def test_review_session_flow(self, db_session, sample_knowledge_units, sample_mastery_records):
        """测试复习会话完整流程"""
        service = ReviewService(db_session)

        # 开始复习
        session = await service.start_review(
            user_id="user1",
            book_id="book1",
            unit_ids=["unit1", "unit2"],
            knowledge_units=sample_knowledge_units,
            review_type="spaced"
        )

        assert isinstance(session, ReviewSession)
        assert len(session.questions) > 0

        # 提交答案
        question = session.questions[0]
        feedback = await service.submit_review_answer(
            session_id=session.id,
            question_id=question.id,
            answer=question.correct_answer,
            user_id="user1",
        )

        assert feedback.is_correct is True
        assert feedback.mastery_change > 0


class TestExamIntegration:
    """考前模式集成测试"""

    @pytest.mark.asyncio
    async def test_exam_flow(self, db_session, sample_knowledge_units, sample_mastery_records):
        """测试考试完整流程"""
        service = ReviewService(db_session)

        config = ExamConfig(
            question_count=5,
            time_limit_minutes=10,
            passing_score=60.0,
            focus_on_weak=True
        )

        # 开始考试
        session = await service.start_exam(
            user_id="user1",
            book_id="book1",
            chapter_ids=["ch1", "ch2"],
            config=config,
            knowledge_units=sample_knowledge_units,
            mastery_records=sample_mastery_records
        )

        assert isinstance(session, ReviewSession)
        assert session.review_type == "exam"

        # 提交考试 - 使用 Dict[str, str] 格式
        answers = {q.id: q.correct_answer for q in session.questions}
        result = await service.submit_exam(
            session_id=session.id,
            answers=answers,
            user_id="user1",
        )

        assert result.passed is True
        assert result.score >= 60.0


class TestKnowledgeGraphIntegration:
    """知识图谱集成测试"""

    @pytest.mark.asyncio
    async def test_build_and_query_graph(self, db_session, sample_knowledge_units):
        """测试图谱构建和查询"""
        service = KnowledgeGraphService(db_session)

        # 构建图谱
        chapters = [
            {"id": "ch1", "title": "第一章"},
            {"id": "ch2", "title": "第二章"}
        ]

        graph = await service.build_graph(
            book_id="book1",
            units=sample_knowledge_units,
            chapters=chapters
        )

        assert isinstance(graph, KnowledgeGraph)
        assert len(graph.nodes) > 0

        # 查询邻居
        if graph.nodes:
            first_node = graph.nodes[0]
            query = GraphQuery(max_depth=2)
            subgraph = await service.query_neighbors("book1", first_node.id, query)

            assert subgraph.center_node.id == first_node.id

    @pytest.mark.asyncio
    async def test_find_path(self, db_session, sample_knowledge_units):
        """测试路径查找"""
        service = KnowledgeGraphService(db_session)

        chapters = [
            {"id": "ch1", "title": "第一章"},
            {"id": "ch2", "title": "第二章"}
        ]

        graph = await service.build_graph(
            book_id="book1",
            units=sample_knowledge_units,
            chapters=chapters
        )

        if len(graph.nodes) >= 2:
            source_id = graph.nodes[0].id
            target_id = graph.nodes[1].id
            path = await service.find_path("book1", source_id, target_id)

            if path:
                assert path[0].source_id == source_id
                assert path[-1].target_id == target_id


class TestExportIntegration:
    """导出功能集成测试"""

    def test_export_markdown(self, sample_knowledge_units, sample_mastery_records):
        """测试Markdown导出"""
        from app.modules.review.exporters import export_markdown

        chapters = [
            {"id": "ch1", "title": "第一章"},
            {"id": "ch2", "title": "第二章"}
        ]

        knowledge_units_dicts = [
            {
                "id": u.id,
                "book_id": u.book_id,
                "chapter_id": u.chapter_id,
                "title": u.title,
                "content": u.content,
                "summary": u.summary,
                "difficulty_level": u.difficulty_level,
                "concepts": u.concepts
            }
            for u in sample_knowledge_units
        ]

        mastery_dict = {
            r.knowledge_unit_id: {
                "mastery_score": r.mastery_score,
                "mastery_level": r.mastery_level
            }
            for r in sample_mastery_records
        }

        result = export_markdown(
            book_title="Python编程入门",
            chapters=chapters,
            knowledge_units=knowledge_units_dicts,
            mastery_records=mastery_dict
        )

        assert isinstance(result.content, str)
        assert len(result.content) > 100

    def test_export_anki(self, sample_knowledge_units, sample_mastery_records):
        """测试Anki导出"""
        from app.modules.review.exporters import export_anki

        knowledge_units_dicts = [
            {
                "id": u.id,
                "book_id": u.book_id,
                "chapter_id": u.chapter_id,
                "title": u.title,
                "content": u.content,
                "summary": u.summary,
                "concepts": u.concepts
            }
            for u in sample_knowledge_units
        ]

        mastery_dict = {
            r.knowledge_unit_id: {
                "mastery_score": r.mastery_score,
                "mastery_level": r.mastery_level
            }
            for r in sample_mastery_records
        }

        result = export_anki(
            book_title="Python编程入门",
            knowledge_units=knowledge_units_dicts,
            mastery_records=mastery_dict
        )

        assert isinstance(result.content, str)
        assert len(result.content) > 0


class TestFullWorkflow:
    """完整工作流集成测试"""

    @pytest.mark.asyncio
    async def test_complete_learning_journey(self, db_session, sample_parsed_document):
        """测试完整学习旅程"""
        # 1. 知识拆分
        splitter = KnowledgeSplitterService()
        split_result = splitter.split(sample_parsed_document, "book1")
        assert len(split_result.units) > 0

        # 2. 获取知识单元
        knowledge_units = split_result.units[:2]  # 只取前两个

        # 3. 复习
        review_service = ReviewService(db_session)
        session = await review_service.start_review(
            user_id="user1",
            book_id="book1",
            unit_ids=[u.id for u in knowledge_units],
            knowledge_units=knowledge_units,
            review_type="spaced"
        )
        assert len(session.questions) > 0

        # 4. 构建知识图谱
        graph_service = KnowledgeGraphService(db_session)
        chapters = [{"id": "ch1", "title": "第一章"}, {"id": "ch2", "title": "第二章"}]
        graph = await graph_service.build_graph(
            book_id="book1",
            units=knowledge_units,
            chapters=chapters
        )
        assert len(graph.nodes) > 0
