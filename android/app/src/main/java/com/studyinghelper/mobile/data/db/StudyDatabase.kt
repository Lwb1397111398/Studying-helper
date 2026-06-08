package com.studyinghelper.mobile.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        BookEntity::class,
        ChapterEntity::class,
        KnowledgeUnitEntity::class,
        KgNodeEntity::class,
        KgEdgeEntity::class,
        MasteryRecordEntity::class,
        AnnotationEntity::class,
        LearningRecordEntity::class,
        DailyStatsEntity::class,
        ReviewSessionEntity::class,
        TeachingSessionEntity::class,
        TeachingMessageEntity::class,
        UserQuestionEntity::class,
        SessionTestEntity::class,
        LearningEfficiencyEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class StudyDatabase : RoomDatabase() {
    abstract fun studyDao(): StudyDao

    companion object {
        @Volatile private var instance: StudyDatabase? = null

        fun getInstance(context: Context): StudyDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    StudyDatabase::class.java,
                    "studying_helper_mobile.db",
                ).build().also { instance = it }
            }
        }
    }
}
