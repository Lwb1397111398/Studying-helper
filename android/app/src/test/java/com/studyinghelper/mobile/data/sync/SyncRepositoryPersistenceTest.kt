package com.studyinghelper.mobile.data.sync

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.repository.AiConfigRepository
import com.studyinghelper.mobile.data.repository.AiRepository
import com.studyinghelper.mobile.data.repository.SyncRepository
import com.studyinghelper.mobile.data.repository.TeachingRepository
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(org.robolectric.RobolectricTestRunner::class)
@org.robolectric.annotation.Config(sdk = [28])
class SyncRepositoryPersistenceTest {
    private lateinit var database: StudyDatabase
    private lateinit var repository: SyncRepository
    private val json = Json { ignoreUnknownKeys = true }

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, StudyDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        repository = SyncRepository(database)
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun importsAndExportsSharedFixturePreservingAidFsrsAndTeachingOrder() = runBlocking {
        val fixture = readSharedFixture()

        val result = repository.importPackage(fixture)
        val dao = database.studyDao()
        val exported = json.decodeFromString<SyncPackage>(repository.exportPackage())
        val teachingState = TeachingRepository(
            database,
            AiRepository(AiConfigRepository(ApplicationProvider.getApplicationContext())),
        ).start("round4-book")

        assertEquals(1, result.books)
        assertEquals(2, result.units)
        assertEquals(1, result.masteryRecords)
        assertEquals(1, result.learnerIntentProfiles)
        assertEquals(1, result.teachingDesigns)
        assertEquals(1, result.moduleMicroPlans)
        assertEquals("memorize", dao.getUnit("round4-unit-b")?.aiCognitiveHint)
        assertEquals("fsrs", dao.getMastery("round4-unit-a")?.algorithm)
        assertEquals(2.5f, dao.getMastery("round4-unit-a")?.stability)
        assertEquals("active", dao.getTeachingDesign("round4-book")?.status)
        assertEquals("[\"round4-unit-b\",\"round4-unit-a\"]", dao.getModuleMicroPlans("round4-book").single().orderedUnitIdsJson)
        assertEquals("memorize", exported.knowledgeUnits.first { it.id == "round4-unit-b" }.aiCognitiveHint)
        assertEquals("fsrs", exported.masteryRecords.single().algorithm)
        assertEquals(listOf("round4-unit-b", "round4-unit-a"), teachingState.units.map { it.id })
        assertTrue(teachingState.session.unitIds.orEmpty().contains("round4-unit-b"))
    }

    private fun readSharedFixture(): String {
        val userDir = File(System.getProperty("user.dir") ?: error("user.dir is not set")).canonicalFile
        val candidates = generateSequence(userDir) { it.parentFile }
            .map { File(it, "docs/samples/round4_sync_package.json").canonicalFile }
            .toList()
        val fixture = candidates.firstOrNull { it.exists() }
            ?: error("Shared fixture not found. Checked: ${candidates.joinToString { it.path }}")
        return fixture.readText(Charsets.UTF_8)
    }
}
