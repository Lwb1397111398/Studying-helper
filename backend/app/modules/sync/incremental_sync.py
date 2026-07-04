"""增量同步服务 - 基于时间戳的智能同步"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ErrorCode, ServiceError
from app.db.models import (
    BookModel, ChapterModel, KnowledgeUnitModel,
    MasteryRecordModel, AnnotationModel, LearningRecordModel,
    DailyStatsModel, ReviewSessionModel, TeachingSessionModel,
    TeachingMessageModel, UserQuestionModel, SessionTestModel,
    LearningEfficiencyModel, KGNodeModel, KGEdgeModel,
)
from app.modules.sync.schemas import SyncPackage


class IncrementalSyncService:
    """增量同步服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_incremental(
        self,
        user_id: str,
        since: datetime,
        book_ids: Optional[List[str]] = None
    ) -> SyncPackage:
        """
        导出自指定时间以来的变更

        Args:
            user_id: 用户 ID
            since: 起始时间
            book_ids: 指定书籍 ID 列表，None 表示所有书籍

        Returns:
            增量同步包
        """
        # 获取用户书籍
        query = select(BookModel).where(BookModel.user_id == user_id)
        if book_ids:
            query = query.where(BookModel.id.in_(book_ids))

        result = await self.db.execute(query)
        books = list(result.scalars().all())

        if not books:
            raise ServiceError(ErrorCode.NOT_FOUND, "没有可导出的书籍")

        book_id_list = [book.id for book in books]

        # 获取变更的章节
        chapters = await self._get_changed_records(
            ChapterModel,
            ChapterModel.book_id.in_(book_id_list),
            since
        )

        # 获取变更的知识单元
        units = await self._get_changed_records(
            KnowledgeUnitModel,
            KnowledgeUnitModel.book_id.in_(book_id_list),
            since
        )
        unit_ids = [unit.id for unit in units]

        # 获取变更的掌握度记录
        mastery_records = await self._get_changed_records(
            MasteryRecordModel,
            and_(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.book_id.in_(book_id_list)
            ),
            since
        )

        # 获取变更的注释
        annotations = []
        if unit_ids:
            annotations = await self._get_changed_records(
                AnnotationModel,
                and_(
                    AnnotationModel.user_id == user_id,
                    AnnotationModel.knowledge_unit_id.in_(unit_ids)
                ),
                since
            )

        # 获取变更的学习记录
        learning_records = await self._get_changed_records(
            LearningRecordModel,
            and_(
                LearningRecordModel.user_id == user_id,
                LearningRecordModel.book_id.in_(book_id_list)
            ),
            since
        )

        # 获取变更的每日统计
        daily_stats = await self._get_changed_records(
            DailyStatsModel,
            DailyStatsModel.user_id == user_id,
            since
        )

        # 获取变更的复习会话
        review_sessions = await self._get_changed_records(
            ReviewSessionModel,
            and_(
                ReviewSessionModel.user_id == user_id,
                ReviewSessionModel.book_id.in_(book_id_list)
            ),
            since
        )

        # 获取变更的教学会话
        teaching_sessions = await self._get_changed_records(
            TeachingSessionModel,
            and_(
                TeachingSessionModel.user_id == user_id,
                TeachingSessionModel.book_id.in_(book_id_list)
            ),
            since
        )
        session_ids = [session.id for session in teaching_sessions]

        # 获取变更的教学消息
        teaching_messages = []
        user_questions = []
        session_tests = []
        learning_efficiency = []
        if session_ids:
            teaching_messages = await self._get_changed_records(
                TeachingMessageModel,
                TeachingMessageModel.session_id.in_(session_ids),
                since
            )
            user_questions = await self._get_changed_records(
                UserQuestionModel,
                UserQuestionModel.session_id.in_(session_ids),
                since
            )
            session_tests = await self._get_changed_records(
                SessionTestModel,
                SessionTestModel.session_id.in_(session_ids),
                since
            )
            learning_efficiency = await self._get_changed_records(
                LearningEfficiencyModel,
                LearningEfficiencyModel.session_id.in_(session_ids),
                since
            )

        # 获取变更的图谱节点和边
        kg_nodes = await self._get_changed_records(
            KGNodeModel,
            KGNodeModel.book_id.in_(book_id_list),
            since
        )
        node_ids = [node.id for node in kg_nodes]

        kg_edges = []
        if node_ids:
            kg_edges = await self._get_changed_records(
                KGEdgeModel,
                or_(
                    KGEdgeModel.source_id.in_(node_ids),
                    KGEdgeModel.target_id.in_(node_ids)
                ),
                since
            )

        # 构建同步包
        return self._build_package(
            user_id=user_id,
            books=books,
            chapters=chapters,
            units=units,
            mastery_records=mastery_records,
            annotations=annotations,
            learning_records=learning_records,
            daily_stats=daily_stats,
            review_sessions=review_sessions,
            teaching_sessions=teaching_sessions,
            teaching_messages=teaching_messages,
            user_questions=user_questions,
            session_tests=session_tests,
            learning_efficiency=learning_efficiency,
            kg_nodes=kg_nodes,
            kg_edges=kg_edges,
        )

    async def import_incremental(
        self,
        user_id: str,
        package: SyncPackage
    ) -> Dict[str, Any]:
        """
        增量导入，智能合并

        Args:
            user_id: 用户 ID
            package: 增量同步包

        Returns:
            导入结果
        """
        if not package.books:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包中没有书籍数据")

        # 验证包的完整性
        self._validate_package_scope(package)

        stats = {
            'inserted': 0,
            'updated': 0,
            'skipped': 0,
            'conflicts': []
        }

        # 处理书籍
        for book_data in package.books:
            existing = await self._get_record(BookModel, book_data.id)
            if existing is None:
                # 新记录，插入
                self._insert_record(BookModel, book_data, user_id)
                stats['inserted'] += 1
            else:
                # 已存在，检查更新时间
                if book_data.updated_at > existing.updated_at:
                    self._update_record(existing, book_data)
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1

        # 处理章节
        for chapter_data in package.chapters:
            existing = await self._get_record(ChapterModel, chapter_data.id)
            if existing is None:
                self._insert_record(ChapterModel, chapter_data)
                stats['inserted'] += 1
            else:
                # 章节通常不更新，跳过
                stats['skipped'] += 1

        # 处理知识单元
        for unit_data in package.knowledge_units:
            existing = await self._get_record(KnowledgeUnitModel, unit_data.id)
            if existing is None:
                self._insert_record(KnowledgeUnitModel, unit_data)
                stats['inserted'] += 1
            else:
                # 知识单元通常不更新，跳过
                stats['skipped'] += 1

        # 处理掌握度记录（需要智能合并）
        for mastery_data in package.mastery_records:
            existing = await self._get_record(MasteryRecordModel, mastery_data.id)
            if existing is None:
                self._insert_record(MasteryRecordModel, mastery_data, user_id)
                stats['inserted'] += 1
            else:
                # 掌握度记录需要合并
                conflict = self._resolve_mastery_conflict(existing, mastery_data)
                if conflict:
                    stats['conflicts'].append(conflict)
                else:
                    stats['updated'] += 1

        # 处理注释
        for annotation_data in package.annotations:
            existing = await self._get_record(AnnotationModel, annotation_data.id)
            if existing is None:
                self._insert_record(AnnotationModel, annotation_data, user_id)
                stats['inserted'] += 1
            else:
                # 注释取更新时间更近的
                if annotation_data.updated_at > existing.updated_at:
                    self._update_record(existing, annotation_data)
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1

        # 处理其他记录（学习记录、每日统计等）
        for record_data in package.learning_records:
            await self._upsert_record(LearningRecordModel, record_data, user_id, stats)

        for stats_data in package.daily_stats:
            await self._upsert_daily_stats(stats_data, user_id, stats)

        for session_data in package.review_sessions:
            await self._upsert_record(ReviewSessionModel, session_data, user_id, stats)

        for session_data in package.teaching_sessions:
            await self._upsert_record(TeachingSessionModel, session_data, user_id, stats)

        for message_data in package.teaching_messages:
            await self._upsert_record(TeachingMessageModel, message_data, None, stats)

        for question_data in package.user_questions:
            await self._upsert_record(UserQuestionModel, question_data, None, stats)

        for test_data in package.session_tests:
            await self._upsert_record(SessionTestModel, test_data, None, stats)

        for efficiency_data in package.learning_efficiency:
            await self._upsert_record(LearningEfficiencyModel, efficiency_data, None, stats)

        for node_data in package.kg_nodes:
            await self._upsert_record(KGNodeModel, node_data, None, stats)

        for edge_data in package.kg_edges:
            await self._upsert_record(KGEdgeModel, edge_data, None, stats)

        await self.db.flush()
        return stats

    async def _get_changed_records(
        self,
        model_class,
        filter_condition,
        since: datetime
    ) -> list:
        """获取自指定时间以来变更的记录"""
        # 注意：这里假设模型有 updated_at 字段
        # 如果没有，则使用 created_at
        time_field = getattr(model_class, 'updated_at', None)
        if time_field is None:
            time_field = getattr(model_class, 'created_at', None)

        if time_field is None:
            # 没有时间字段，返回所有记录
            query = select(model_class).where(filter_condition)
        else:
            query = select(model_class).where(
                and_(filter_condition, time_field >= since)
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_record(self, model_class, record_id: str):
        """获取单条记录"""
        result = await self.db.execute(
            select(model_class).where(model_class.id == record_id)
        )
        return result.scalar_one_or_none()

    def _insert_record(self, model_class, data, user_id: str = None):
        """插入新记录"""
        record_data = data.model_dump()
        if user_id and 'user_id' in record_data:
            record_data['user_id'] = user_id
        self.db.add(model_class(**record_data))

    def _update_record(self, existing, new_data):
        """更新现有记录"""
        update_data = new_data.model_dump()
        for key, value in update_data.items():
            if hasattr(existing, key) and key != 'id':
                setattr(existing, key, value)

    async def _upsert_record(self, model_class, data, user_id: str, stats: dict):
        """插入或更新记录"""
        existing = await self._get_record(model_class, data.id)
        if existing is None:
            self._insert_record(model_class, data, user_id)
            stats['inserted'] += 1
        else:
            self._update_record(existing, data)
            stats['updated'] += 1

    async def _upsert_daily_stats(self, stats_data, user_id: str, stats: dict):
        """插入或更新每日统计"""
        result = await self.db.execute(
            select(DailyStatsModel).where(
                and_(
                    DailyStatsModel.user_id == user_id,
                    DailyStatsModel.date == stats_data.date
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            self._insert_record(DailyStatsModel, stats_data, user_id)
            stats['inserted'] += 1
        else:
            # 每日统计需要合并
            self._merge_daily_stats(existing, stats_data)
            stats['updated'] += 1

    def _merge_daily_stats(self, existing, new_data):
        """合并每日统计"""
        # 取各字段的最大值或最新值
        existing.total_minutes = max(existing.total_minutes or 0, new_data.total_minutes or 0)
        existing.units_learned = max(existing.units_learned or 0, new_data.units_learned or 0)
        existing.units_reviewed = max(existing.units_reviewed or 0, new_data.units_reviewed or 0)
        existing.tests_taken = max(existing.tests_taken or 0, new_data.tests_taken or 0)
        existing.avg_test_score = max(existing.avg_test_score or 0, new_data.avg_test_score or 0)
        existing.streak_day = max(existing.streak_day or 0, new_data.streak_day or 0)

    def _resolve_mastery_conflict(self, existing, new_data) -> Optional[Dict]:
        """解决掌握度记录冲突"""
        # 策略：保留复习次数更多的（更可靠的数据）
        if existing.review_count != new_data.review_count:
            if new_data.review_count > existing.review_count:
                self._update_record(existing, new_data)
                return None
            else:
                return {
                    'type': 'mastery_conflict',
                    'id': existing.id,
                    'resolution': 'kept_local',
                    'reason': 'local_has_more_reviews'
                }

        # 次选：保留更新时间更近的
        if new_data.last_reviewed_at and existing.last_reviewed_at:
            if new_data.last_reviewed_at > existing.last_reviewed_at:
                self._update_record(existing, new_data)
                return None

        return {
            'type': 'mastery_conflict',
            'id': existing.id,
            'resolution': 'kept_local',
            'reason': 'same_review_count'
        }

    def _validate_package_scope(self, package: SyncPackage) -> None:
        """验证同步包的完整性"""
        book_ids = {book.id for book in package.books}
        chapter_ids = {chapter.id for chapter in package.chapters}
        unit_ids = {unit.id for unit in package.knowledge_units}
        node_ids = {node.id for node in package.kg_nodes}
        session_ids = {session.id for session in package.teaching_sessions}

        for chapter in package.chapters:
            if chapter.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的章节")

        for unit in package.knowledge_units:
            if unit.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的知识单元")
            if unit.chapter_id not in chapter_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入章节的知识单元")

        for record in package.mastery_records:
            if record.book_id not in book_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的掌握度记录")
            if record.knowledge_unit_id not in unit_ids:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "同步包包含不属于导入书籍的掌握度记录")

    def _build_package(self, user_id: str, **kwargs) -> SyncPackage:
        """构建同步包"""
        from app.modules.sync.schemas import (
            SyncBook, SyncChapter, SyncKnowledgeUnit,
            SyncMasteryRecord, SyncAnnotation, SyncLearningRecord,
            SyncDailyStats, SyncReviewSession, SyncTeachingSession,
            SyncTeachingMessage, SyncUserQuestion, SyncSessionTest,
            SyncLearningEfficiency, SyncKGNode, SyncKGEdge,
        )

        return SyncPackage(
            user_id=user_id,
            source="web",
            books=[self._to_schema(SyncBook, item) for item in kwargs.get('books', [])],
            chapters=[self._to_schema(SyncChapter, item) for item in kwargs.get('chapters', [])],
            knowledge_units=[self._to_schema(SyncKnowledgeUnit, item) for item in kwargs.get('units', [])],
            kg_nodes=[self._to_schema(SyncKGNode, item) for item in kwargs.get('kg_nodes', [])],
            kg_edges=[self._to_schema(SyncKGEdge, item) for item in kwargs.get('kg_edges', [])],
            mastery_records=[self._to_schema(SyncMasteryRecord, item) for item in kwargs.get('mastery_records', [])],
            annotations=[self._to_schema(SyncAnnotation, item) for item in kwargs.get('annotations', [])],
            learning_records=[self._to_schema(SyncLearningRecord, item) for item in kwargs.get('learning_records', [])],
            daily_stats=[self._to_schema(SyncDailyStats, item) for item in kwargs.get('daily_stats', [])],
            review_sessions=[self._to_schema(SyncReviewSession, item) for item in kwargs.get('review_sessions', [])],
            teaching_sessions=[self._to_schema(SyncTeachingSession, item) for item in kwargs.get('teaching_sessions', [])],
            teaching_messages=[self._to_schema(SyncTeachingMessage, item) for item in kwargs.get('teaching_messages', [])],
            user_questions=[self._to_schema(SyncUserQuestion, item) for item in kwargs.get('user_questions', [])],
            session_tests=[self._to_schema(SyncSessionTest, item) for item in kwargs.get('session_tests', [])],
            learning_efficiency=[self._to_schema(SyncLearningEfficiency, item) for item in kwargs.get('learning_efficiency', [])],
        )

    def _to_schema(self, schema_class, model):
        """将 ORM 模型转换为 Pydantic schema"""
        data = {field: getattr(model, field) for field in schema_class.model_fields}
        return schema_class(**data)
