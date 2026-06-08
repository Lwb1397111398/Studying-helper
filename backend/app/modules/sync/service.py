"""数据同步服务"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ErrorCode, ServiceError
from app.db.models import (
    AnnotationModel,
    BookModel,
    ChapterModel,
    DailyStatsModel,
    KGEdgeModel,
    KGNodeModel,
    KnowledgeUnitModel,
    LearningEfficiencyModel,
    LearningRecordModel,
    MasteryRecordModel,
    ReviewSessionModel,
    SessionTestModel,
    TeachingMessageModel,
    TeachingSessionModel,
    UserQuestionModel,
)
from app.modules.sync.schemas import (
    SCHEMA_VERSION,
    SyncAnnotation,
    SyncBook,
    SyncChapter,
    SyncDailyStats,
    SyncImportResult,
    SyncKGEdge,
    SyncKGNode,
    SyncKnowledgeUnit,
    SyncLearningEfficiency,
    SyncLearningRecord,
    SyncMasteryRecord,
    SyncPackage,
    SyncPreviewBook,
    SyncPreviewResult,
    SyncReviewSession,
    SyncSessionTest,
    SyncTeachingMessage,
    SyncTeachingSession,
    SyncUserQuestion,
)


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_all(self, user_id: str) -> SyncPackage:
        books = await self._fetch_all(select(BookModel).where(BookModel.user_id == user_id))
        if not books:
            raise ServiceError(ErrorCode.NOT_FOUND, "没有可导出的书籍")
        return await self._build_package(user_id, books, include_daily_stats=True)

    async def export_book(self, user_id: str, book_id: str) -> SyncPackage:
        book = await self._get_user_book(user_id, book_id)
        return await self._build_package(user_id, [book], include_daily_stats=False)

    async def preview_package(self, package: SyncPackage) -> SyncPreviewResult:
        if package.schema_version != SCHEMA_VERSION:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"不支持的同步包版本: {package.schema_version}",
            )
        if not package.books:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包中没有书籍数据")
        self._validate_package_scope(package)

        book_ids = [book.id for book in package.books]
        local_books = {}
        result = await self.db.execute(select(BookModel).where(BookModel.id.in_(book_ids)))
        for book in result.scalars().all():
            local_books[book.id] = book

        return SyncPreviewResult(
            schema_version=package.schema_version,
            source=package.source,
            exported_at=package.exported_at,
            books_count=len(package.books),
            chapters_count=len(package.chapters),
            units_count=len(package.knowledge_units),
            mastery_records_count=len(package.mastery_records),
            annotations_count=len(package.annotations),
            kg_nodes_count=len(package.kg_nodes),
            kg_edges_count=len(package.kg_edges),
            daily_stats_count=len(package.daily_stats),
            learning_records_count=len(package.learning_records),
            review_sessions_count=len(package.review_sessions),
            teaching_sessions_count=len(package.teaching_sessions),
            teaching_messages_count=len(package.teaching_messages),
            user_questions_count=len(package.user_questions),
            session_tests_count=len(package.session_tests),
            learning_efficiency_count=len(package.learning_efficiency),
            books=[
                SyncPreviewBook(
                    id=book.id,
                    title=book.title,
                    source_updated_at=book.updated_at,
                    will_overwrite=book.id in local_books,
                    local_title=local_books[book.id].title if book.id in local_books else None,
                )
                for book in package.books
            ],
        )

    async def import_package(self, user_id: str, package: SyncPackage) -> SyncImportResult:
        if package.schema_version != SCHEMA_VERSION:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"不支持的同步包版本: {package.schema_version}",
            )
        if not package.books:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包中没有书籍数据")
        self._validate_package_scope(package)

        book_ids = [book.id for book in package.books]
        overwritten_books = []
        for book_id in book_ids:
            if await self._book_exists(book_id):
                overwritten_books.append(book_id)
            await self._delete_book_data(book_id)

        dates = [stats.date for stats in package.daily_stats]
        if dates:
            await self.db.execute(
                delete(DailyStatsModel).where(
                    DailyStatsModel.user_id == user_id,
                    DailyStatsModel.date.in_(dates),
                )
            )

        self._add_models(BookModel, package.books, user_id=user_id)
        self._add_models(ChapterModel, package.chapters)
        self._add_models(KnowledgeUnitModel, package.knowledge_units)
        self._add_models(KGNodeModel, package.kg_nodes)
        self._add_models(KGEdgeModel, package.kg_edges)
        self._add_models(MasteryRecordModel, package.mastery_records, user_id=user_id)
        self._add_models(AnnotationModel, package.annotations, user_id=user_id)
        self._add_models(LearningRecordModel, package.learning_records, user_id=user_id)
        self._add_models(DailyStatsModel, package.daily_stats, user_id=user_id)
        self._add_models(ReviewSessionModel, package.review_sessions, user_id=user_id)
        self._add_models(TeachingSessionModel, package.teaching_sessions, user_id=user_id)
        self._add_models(TeachingMessageModel, package.teaching_messages)
        self._add_models(UserQuestionModel, package.user_questions)
        self._add_models(SessionTestModel, package.session_tests)
        self._add_models(LearningEfficiencyModel, package.learning_efficiency)

        await self.db.flush()
        return SyncImportResult(
            books_imported=len(package.books),
            chapters_imported=len(package.chapters),
            units_imported=len(package.knowledge_units),
            mastery_records_imported=len(package.mastery_records),
            overwritten_books=overwritten_books,
            annotations_imported=len(package.annotations),
            kg_nodes_imported=len(package.kg_nodes),
            kg_edges_imported=len(package.kg_edges),
            learning_records_imported=len(package.learning_records),
            daily_stats_imported=len(package.daily_stats),
            review_sessions_imported=len(package.review_sessions),
            teaching_sessions_imported=len(package.teaching_sessions),
            teaching_messages_imported=len(package.teaching_messages),
            user_questions_imported=len(package.user_questions),
            session_tests_imported=len(package.session_tests),
            learning_efficiency_imported=len(package.learning_efficiency),
        )

    def _validate_package_scope(self, package: SyncPackage) -> None:
        book_ids = {book.id for book in package.books}
        chapter_ids = {chapter.id for chapter in package.chapters}
        unit_ids = {unit.id for unit in package.knowledge_units}
        node_ids = {node.id for node in package.kg_nodes}
        teaching_session_ids = {session.id for session in package.teaching_sessions}

        for chapter in package.chapters:
            if chapter.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的章节")
            if chapter.parent_id is not None and chapter.parent_id not in chapter_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入章节树的父章节")
        for unit in package.knowledge_units:
            if unit.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的知识单元")
            if unit.chapter_id not in chapter_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入章节的知识单元")
        for node in package.kg_nodes:
            if node.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的图谱节点")
        for edge in package.kg_edges:
            if edge.source_id not in node_ids or edge.target_id not in node_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入图谱的关系")
        for record in package.mastery_records:
            if record.book_id not in book_ids or record.knowledge_unit_id not in unit_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的掌握度记录")
        for annotation in package.annotations:
            if annotation.knowledge_unit_id not in unit_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的注释")
        for record in package.learning_records:
            if record.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的学习记录")
        for session in package.review_sessions:
            if session.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的复习记录")
        for session in package.teaching_sessions:
            if session.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的教学会话")
        for message in package.teaching_messages:
            if message.session_id not in teaching_session_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入教学会话的教学消息")
        for question in package.user_questions:
            if question.session_id not in teaching_session_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入教学会话的用户提问")
        for test in package.session_tests:
            if test.session_id not in teaching_session_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入教学会话的阶段测试")
        for efficiency in package.learning_efficiency:
            if efficiency.session_id not in teaching_session_ids or efficiency.unit_id not in unit_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入范围的学习效率记录")

    async def _build_package(
        self,
        user_id: str,
        books: list[BookModel],
        include_daily_stats: bool,
    ) -> SyncPackage:
        book_ids = [book.id for book in books]
        chapters = await self._fetch_all(select(ChapterModel).where(ChapterModel.book_id.in_(book_ids)))
        units = await self._fetch_all(select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id.in_(book_ids)))
        unit_ids = [unit.id for unit in units]

        nodes = await self._fetch_all(select(KGNodeModel).where(KGNodeModel.book_id.in_(book_ids)))
        node_ids = [node.id for node in nodes]
        edges = []
        if node_ids:
            edges = await self._fetch_all(
                select(KGEdgeModel).where(
                    KGEdgeModel.source_id.in_(node_ids),
                    KGEdgeModel.target_id.in_(node_ids),
                )
            )

        mastery_records = await self._fetch_all(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.book_id.in_(book_ids),
            )
        )
        annotations = []
        if unit_ids:
            annotations = await self._fetch_all(
                select(AnnotationModel).where(
                    AnnotationModel.user_id == user_id,
                    AnnotationModel.knowledge_unit_id.in_(unit_ids),
                )
            )

        learning_records = await self._fetch_all(
            select(LearningRecordModel).where(
                LearningRecordModel.user_id == user_id,
                LearningRecordModel.book_id.in_(book_ids),
            )
        )
        daily_stats = []
        if include_daily_stats:
            daily_stats = await self._fetch_all(select(DailyStatsModel).where(DailyStatsModel.user_id == user_id))
        review_sessions = await self._fetch_all(
            select(ReviewSessionModel).where(
                ReviewSessionModel.user_id == user_id,
                ReviewSessionModel.book_id.in_(book_ids),
            )
        )
        teaching_sessions = await self._fetch_all(
            select(TeachingSessionModel).where(
                TeachingSessionModel.user_id == user_id,
                TeachingSessionModel.book_id.in_(book_ids),
            )
        )
        session_ids = [session.id for session in teaching_sessions]
        teaching_messages = []
        user_questions = []
        session_tests = []
        learning_efficiency = []
        if session_ids:
            teaching_messages = await self._fetch_all(
                select(TeachingMessageModel).where(TeachingMessageModel.session_id.in_(session_ids))
            )
            user_questions = await self._fetch_all(
                select(UserQuestionModel).where(UserQuestionModel.session_id.in_(session_ids))
            )
            session_tests = await self._fetch_all(
                select(SessionTestModel).where(SessionTestModel.session_id.in_(session_ids))
            )
            learning_efficiency = await self._fetch_all(
                select(LearningEfficiencyModel).where(LearningEfficiencyModel.session_id.in_(session_ids))
            )

        return SyncPackage(
            user_id=user_id,
            books=[self._to_schema(SyncBook, item) for item in books],
            chapters=[self._to_schema(SyncChapter, item) for item in chapters],
            knowledge_units=[self._to_schema(SyncKnowledgeUnit, item) for item in units],
            kg_nodes=[self._to_schema(SyncKGNode, item) for item in nodes],
            kg_edges=[self._to_schema(SyncKGEdge, item) for item in edges],
            mastery_records=[self._to_schema(SyncMasteryRecord, item) for item in mastery_records],
            annotations=[self._to_schema(SyncAnnotation, item) for item in annotations],
            learning_records=[self._to_schema(SyncLearningRecord, item) for item in learning_records],
            daily_stats=[self._to_schema(SyncDailyStats, item) for item in daily_stats],
            review_sessions=[self._to_schema(SyncReviewSession, item) for item in review_sessions],
            teaching_sessions=[self._to_schema(SyncTeachingSession, item) for item in teaching_sessions],
            teaching_messages=[self._to_schema(SyncTeachingMessage, item) for item in teaching_messages],
            user_questions=[self._to_schema(SyncUserQuestion, item) for item in user_questions],
            session_tests=[self._to_schema(SyncSessionTest, item) for item in session_tests],
            learning_efficiency=[self._to_schema(SyncLearningEfficiency, item) for item in learning_efficiency],
        )

    async def _book_exists(self, book_id: str) -> bool:
        result = await self.db.execute(select(BookModel.id).where(BookModel.id == book_id))
        return result.scalar_one_or_none() is not None

    async def _get_user_book(self, user_id: str, book_id: str) -> BookModel:
        result = await self.db.execute(select(BookModel).where(BookModel.id == book_id))
        book = result.scalar_one_or_none()
        if book is None or book.user_id != user_id:
            raise ServiceError(ErrorCode.NOT_FOUND, f"书籍 {book_id} 不存在")
        return book

    async def _delete_book_data(self, book_id: str) -> None:
        result = await self.db.execute(select(BookModel).where(BookModel.id == book_id))
        book = result.scalar_one_or_none()
        if book is None:
            return

        unit_ids = [
            row[0]
            for row in (
                await self.db.execute(select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id))
            ).all()
        ]
        node_ids = [
            row[0]
            for row in (
                await self.db.execute(select(KGNodeModel.id).where(KGNodeModel.book_id == book_id))
            ).all()
        ]
        session_ids = [
            row[0]
            for row in (
                await self.db.execute(select(TeachingSessionModel.id).where(TeachingSessionModel.book_id == book_id))
            ).all()
        ]

        if unit_ids:
            await self.db.execute(delete(AnnotationModel).where(AnnotationModel.knowledge_unit_id.in_(unit_ids)))
            await self.db.execute(delete(MasteryRecordModel).where(MasteryRecordModel.knowledge_unit_id.in_(unit_ids)))
        if node_ids:
            await self.db.execute(
                delete(KGEdgeModel).where(
                    (KGEdgeModel.source_id.in_(node_ids)) | (KGEdgeModel.target_id.in_(node_ids))
                )
            )
        if session_ids:
            await self.db.execute(delete(TeachingMessageModel).where(TeachingMessageModel.session_id.in_(session_ids)))
            await self.db.execute(delete(UserQuestionModel).where(UserQuestionModel.session_id.in_(session_ids)))
            await self.db.execute(delete(SessionTestModel).where(SessionTestModel.session_id.in_(session_ids)))
            await self.db.execute(delete(LearningEfficiencyModel).where(LearningEfficiencyModel.session_id.in_(session_ids)))

        await self.db.execute(delete(ReviewSessionModel).where(ReviewSessionModel.book_id == book_id))
        await self.db.execute(delete(TeachingSessionModel).where(TeachingSessionModel.book_id == book_id))
        await self.db.execute(delete(LearningRecordModel).where(LearningRecordModel.book_id == book_id))
        await self.db.execute(delete(KGNodeModel).where(KGNodeModel.book_id == book_id))
        await self.db.execute(delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id))
        await self.db.execute(delete(ChapterModel).where(ChapterModel.book_id == book_id))
        await self.db.delete(book)

    async def _fetch_all(self, statement):
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    def _add_models(self, model_class, items, user_id: str | None = None) -> None:
        for item in items:
            data = item.model_dump()
            if user_id is not None and "user_id" in data:
                data["user_id"] = user_id
            self.db.add(model_class(**data))

    def _to_schema(self, schema_class, model):
        data = {field: getattr(model, field) for field in schema_class.model_fields}
        return schema_class(**data)
