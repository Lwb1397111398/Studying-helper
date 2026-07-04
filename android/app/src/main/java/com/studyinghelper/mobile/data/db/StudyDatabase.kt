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
        LearnerIntentProfileEntity::class,
        TeachingDesignEntity::class,
        ModuleMicroPlanEntity::class,
    ],
    version = 2,
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
                )
                    .addMigrations(MIGRATION_1_2)
                    .build()
                    .also { instance = it }
            }
        }
    }
}
