package com.studyinghelper.mobile.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface StudyDao {
    @Query("SELECT * FROM books ORDER BY updated_at DESC")
    fun observeBooks(): Flow<List<BookEntity>>

    @Query("SELECT * FROM books WHERE id = :bookId")
    fun observeBook(bookId: String): Flow<BookEntity?>

    @Query("SELECT * FROM chapters WHERE book_id = :bookId ORDER BY order_index")
    fun observeChapters(bookId: String): Flow<List<ChapterEntity>>

    @Query("SELECT * FROM knowledge_units WHERE book_id = :bookId ORDER BY order_index")
    fun observeUnits(bookId: String): Flow<List<KnowledgeUnitEntity>>

    @Query("SELECT * FROM knowledge_units WHERE id = :unitId")
    fun observeUnit(unitId: String): Flow<KnowledgeUnitEntity?>

    @Query("SELECT * FROM mastery_records WHERE knowledge_unit_id = :unitId LIMIT 1")
    fun observeMastery(unitId: String): Flow<MasteryRecordEntity?>

    @Query("SELECT knowledge_units.* FROM knowledge_units LEFT JOIN mastery_records ON mastery_records.knowledge_unit_id = knowledge_units.id WHERE knowledge_units.book_id = :bookId AND (mastery_records.id IS NULL OR julianday(mastery_records.next_review_at) <= julianday(:now)) ORDER BY knowledge_units.order_index")
    fun observeDueUnits(bookId: String, now: String): Flow<List<KnowledgeUnitEntity>>

    @Query("SELECT COUNT(*) FROM books")
    suspend fun countBooks(): Int

    @Query("SELECT COUNT(*) FROM knowledge_units")
    suspend fun countAllUnits(): Int

    @Query("SELECT COUNT(DISTINCT knowledge_unit_id) FROM mastery_records WHERE mastery_score >= 0.6")
    suspend fun countAllLearnedUnits(): Int

    @Query("SELECT COUNT(*) FROM review_sessions")
    suspend fun countReviewSessions(): Int

    @Query("SELECT COUNT(*) FROM review_sessions WHERE review_type = 'exam'")
    suspend fun countExamSessions(): Int

    @Query("SELECT SUM(total_minutes) FROM daily_stats")
    suspend fun sumStudyMinutes(): Int?

    @Query("SELECT * FROM books WHERE id = :bookId LIMIT 1")
    suspend fun getBook(bookId: String): BookEntity?

    @Query("SELECT * FROM knowledge_units WHERE id = :unitId LIMIT 1")
    suspend fun getUnit(unitId: String): KnowledgeUnitEntity?

    @Query("SELECT * FROM knowledge_units WHERE book_id = :bookId ORDER BY order_index")
    suspend fun getUnits(bookId: String): List<KnowledgeUnitEntity>

    @Query("SELECT * FROM mastery_records WHERE knowledge_unit_id = :unitId LIMIT 1")
    suspend fun getMastery(unitId: String): MasteryRecordEntity?

    @Query("SELECT * FROM daily_stats WHERE user_id = :userId AND date = :date LIMIT 1")
    suspend fun getDailyStats(userId: String, date: String): DailyStatsEntity?

    @Query("SELECT COUNT(*) FROM chapters WHERE book_id = :bookId")
    suspend fun countChapters(bookId: String): Int

    @Query("SELECT COUNT(*) FROM knowledge_units WHERE book_id = :bookId")
    suspend fun countUnits(bookId: String): Int

    @Query("SELECT COUNT(DISTINCT knowledge_unit_id) FROM mastery_records WHERE book_id = :bookId AND mastery_score >= 0.6")
    suspend fun countLearnedUnits(bookId: String): Int

    @Query("SELECT * FROM chapters WHERE book_id = :bookId ORDER BY order_index LIMIT 1")
    suspend fun getFirstChapter(bookId: String): ChapterEntity?

    @Query("UPDATE books SET total_chapters = :chapters, total_units = :units, learned_units = :learned, learn_status = :learnStatus, updated_at = :updatedAt WHERE id = :bookId")
    suspend fun updateBookCounts(bookId: String, chapters: Int, units: Int, learned: Int, learnStatus: String, updatedAt: String)

    @Query("UPDATE knowledge_units SET summary = :summary, explanation = :explanation, key_points = :keyPoints, concepts = :concepts WHERE id = :unitId")
    suspend fun updateUnitAnalysis(unitId: String, summary: String, explanation: String, keyPoints: String, concepts: String)

    @Query("SELECT * FROM books")
    suspend fun getBooks(): List<BookEntity>

    @Query("SELECT * FROM chapters")
    suspend fun getChapters(): List<ChapterEntity>

    @Query("SELECT * FROM knowledge_units")
    suspend fun getKnowledgeUnits(): List<KnowledgeUnitEntity>

    @Query("SELECT * FROM kg_nodes")
    suspend fun getKgNodes(): List<KgNodeEntity>

    @Query("SELECT * FROM kg_edges")
    suspend fun getKgEdges(): List<KgEdgeEntity>

    @Query("SELECT * FROM mastery_records")
    suspend fun getMasteryRecords(): List<MasteryRecordEntity>

    @Query("SELECT * FROM annotations")
    suspend fun getAnnotations(): List<AnnotationEntity>

    @Query("SELECT * FROM learning_records")
    suspend fun getLearningRecords(): List<LearningRecordEntity>

    @Query("SELECT * FROM daily_stats")
    suspend fun getDailyStats(): List<DailyStatsEntity>

    @Query("SELECT * FROM review_sessions")
    suspend fun getReviewSessions(): List<ReviewSessionEntity>

    @Query("SELECT * FROM teaching_sessions")
    suspend fun getTeachingSessions(): List<TeachingSessionEntity>

    @Query("SELECT * FROM teaching_messages")
    suspend fun getTeachingMessages(): List<TeachingMessageEntity>

    @Query("SELECT * FROM user_questions")
    suspend fun getUserQuestions(): List<UserQuestionEntity>

    @Query("SELECT * FROM session_tests")
    suspend fun getSessionTests(): List<SessionTestEntity>

    @Query("SELECT * FROM learning_efficiency")
    suspend fun getLearningEfficiency(): List<LearningEfficiencyEntity>

    @Query("DELETE FROM books WHERE id IN (:bookIds)")
    suspend fun deleteBooks(bookIds: List<String>)

    @Query("DELETE FROM chapters WHERE book_id IN (:bookIds)")
    suspend fun deleteChapters(bookIds: List<String>)

    @Query("DELETE FROM knowledge_units WHERE book_id IN (:bookIds)")
    suspend fun deleteUnits(bookIds: List<String>)

    @Query("DELETE FROM kg_nodes WHERE book_id IN (:bookIds)")
    suspend fun deleteKgNodes(bookIds: List<String>)

    @Query("DELETE FROM mastery_records WHERE book_id IN (:bookIds)")
    suspend fun deleteMastery(bookIds: List<String>)

    @Query("DELETE FROM learning_records WHERE book_id IN (:bookIds)")
    suspend fun deleteLearningRecords(bookIds: List<String>)

    @Query("DELETE FROM review_sessions WHERE book_id IN (:bookIds)")
    suspend fun deleteReviewSessions(bookIds: List<String>)

    @Query("DELETE FROM teaching_sessions WHERE book_id IN (:bookIds)")
    suspend fun deleteTeachingSessions(bookIds: List<String>)

    @Query("DELETE FROM annotations WHERE knowledge_unit_id IN (:unitIds)")
    suspend fun deleteAnnotations(unitIds: List<String>)

    @Query("DELETE FROM kg_edges WHERE source_id IN (:nodeIds) OR target_id IN (:nodeIds)")
    suspend fun deleteKgEdges(nodeIds: List<String>)

    @Query("DELETE FROM teaching_messages WHERE session_id IN (:sessionIds)")
    suspend fun deleteTeachingMessages(sessionIds: List<String>)

    @Query("DELETE FROM user_questions WHERE session_id IN (:sessionIds)")
    suspend fun deleteUserQuestions(sessionIds: List<String>)

    @Query("DELETE FROM session_tests WHERE session_id IN (:sessionIds)")
    suspend fun deleteSessionTests(sessionIds: List<String>)

    @Query("DELETE FROM learning_efficiency WHERE session_id IN (:sessionIds)")
    suspend fun deleteLearningEfficiency(sessionIds: List<String>)

    @Query("DELETE FROM daily_stats WHERE user_id = :userId AND date IN (:dates)")
    suspend fun deleteDailyStats(userId: String, dates: List<String>)

    @Query("SELECT id FROM knowledge_units WHERE book_id IN (:bookIds)")
    suspend fun getUnitIds(bookIds: List<String>): List<String>

    @Query("SELECT id FROM kg_nodes WHERE book_id IN (:bookIds)")
    suspend fun getNodeIds(bookIds: List<String>): List<String>

    @Query("SELECT id FROM teaching_sessions WHERE book_id IN (:bookIds)")
    suspend fun getTeachingSessionIds(bookIds: List<String>): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertBooks(items: List<BookEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertChapters(items: List<ChapterEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertUnits(items: List<KnowledgeUnitEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertKgNodes(items: List<KgNodeEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertKgEdges(items: List<KgEdgeEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertMastery(items: List<MasteryRecordEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAnnotations(items: List<AnnotationEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLearningRecords(items: List<LearningRecordEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertDailyStats(items: List<DailyStatsEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertReviewSessions(items: List<ReviewSessionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTeachingSessions(items: List<TeachingSessionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTeachingMessages(items: List<TeachingMessageEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertUserQuestions(items: List<UserQuestionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSessionTests(items: List<SessionTestEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLearningEfficiency(items: List<LearningEfficiencyEntity>)
}
