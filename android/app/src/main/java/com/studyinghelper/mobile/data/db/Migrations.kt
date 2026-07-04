package com.studyinghelper.mobile.data.db

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

internal val MIGRATION_1_2_STATEMENTS = listOf(
    "ALTER TABLE knowledge_units ADD COLUMN ai_cognitive_hint TEXT",
    "ALTER TABLE mastery_records ADD COLUMN stability REAL NOT NULL DEFAULT 0.0",
    "ALTER TABLE mastery_records ADD COLUMN difficulty REAL NOT NULL DEFAULT 5.0",
    "ALTER TABLE mastery_records ADD COLUMN lapses INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE mastery_records ADD COLUMN reps INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE mastery_records ADD COLUMN last_elapsed_days INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE mastery_records ADD COLUMN scheduled_days INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE mastery_records ADD COLUMN algorithm TEXT NOT NULL DEFAULT 'sm2'",
    """
    CREATE TABLE IF NOT EXISTS learner_intent_profiles (
        id TEXT NOT NULL PRIMARY KEY,
        user_id TEXT NOT NULL,
        book_id TEXT NOT NULL,
        identity_background TEXT NOT NULL,
        goal_depth TEXT NOT NULL,
        cognitive_pref TEXT NOT NULL,
        restructure_tolerance TEXT NOT NULL,
        time_budget_minutes INTEGER,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        extra_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """.trimIndent(),
    """
    CREATE TABLE IF NOT EXISTS teaching_designs (
        id TEXT NOT NULL PRIMARY KEY,
        user_id TEXT NOT NULL,
        book_id TEXT NOT NULL,
        profile_id TEXT,
        macro_design_json TEXT,
        current_module_index INTEGER NOT NULL,
        generated_module_count INTEGER NOT NULL,
        adjustments_json TEXT NOT NULL,
        status TEXT NOT NULL,
        version INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """.trimIndent(),
    """
    CREATE TABLE IF NOT EXISTS module_micro_plans (
        id TEXT NOT NULL PRIMARY KEY,
        design_id TEXT NOT NULL,
        book_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        module_index INTEGER NOT NULL,
        module_title TEXT NOT NULL,
        ordered_unit_ids_json TEXT NOT NULL,
        unit_annotations_json TEXT NOT NULL,
        module_intro TEXT,
        module_status TEXT NOT NULL,
        module_summary_json TEXT,
        parent_design_version INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """.trimIndent(),
    "CREATE UNIQUE INDEX IF NOT EXISTS index_learner_intent_profiles_user_id_book_id ON learner_intent_profiles(user_id, book_id)",
    "CREATE INDEX IF NOT EXISTS index_learner_intent_profiles_book_id ON learner_intent_profiles(book_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS index_teaching_designs_user_id_book_id_version ON teaching_designs(user_id, book_id, version)",
    "CREATE INDEX IF NOT EXISTS index_teaching_designs_book_id ON teaching_designs(book_id)",
    "CREATE INDEX IF NOT EXISTS index_teaching_designs_status ON teaching_designs(status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS index_module_micro_plans_design_id_module_index ON module_micro_plans(design_id, module_index)",
    "CREATE INDEX IF NOT EXISTS index_module_micro_plans_book_id_module_status ON module_micro_plans(book_id, module_status)",
)

internal val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        MIGRATION_1_2_STATEMENTS.forEach(db::execSQL)
    }
}
