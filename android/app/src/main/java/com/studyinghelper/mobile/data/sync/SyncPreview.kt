package com.studyinghelper.mobile.data.sync

data class SyncPreview(
    val source: String,
    val books: Int,
    val units: Int,
    val masteryRecords: Int,
    val overwrittenBooks: Int,
) {
    companion object {
        fun fromPackage(packageData: SyncPackage, localBookIds: Set<String>): SyncPreview {
            return SyncPreview(
                source = packageData.source,
                books = packageData.books.size,
                units = packageData.knowledgeUnits.size,
                masteryRecords = packageData.masteryRecords.size,
                overwrittenBooks = packageData.books.count { it.id in localBookIds },
            )
        }
    }
}
