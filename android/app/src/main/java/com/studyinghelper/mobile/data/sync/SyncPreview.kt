package com.studyinghelper.mobile.data.sync

data class SyncPreview(
    val source: String,
    val books: Int,
    val chapters: Int,
    val units: Int,
    val masteryRecords: Int,
    val reviewSessions: Int,
    val teachingSessions: Int,
    val teachingMessages: Int,
    val learnerIntentProfiles: Int,
    val teachingDesigns: Int,
    val moduleMicroPlans: Int,
    val overwrittenBooks: Int,
) {
    companion object {
        fun fromPackage(packageData: SyncPackage, localBookIds: Set<String>): SyncPreview {
            return SyncPreview(
                source = packageData.source,
                books = packageData.books.size,
                chapters = packageData.chapters.size,
                units = packageData.knowledgeUnits.size,
                masteryRecords = packageData.masteryRecords.size,
                reviewSessions = packageData.reviewSessions.size,
                teachingSessions = packageData.teachingSessions.size,
                teachingMessages = packageData.teachingMessages.size,
                learnerIntentProfiles = packageData.learnerIntentProfiles.size,
                teachingDesigns = packageData.teachingDesigns.size,
                moduleMicroPlans = packageData.moduleMicroPlans.size,
                overwrittenBooks = packageData.books.count { it.id in localBookIds },
            )
        }
    }
}
