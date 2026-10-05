package com.studyinghelper.mobile.data.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File

/**
 * 唤起系统安装器安装更新 APK；处理「安装未知应用」授权跳转。
 */
object UpdateInstaller {

    private const val AUTHORITY_SUFFIX = ".update"

    /** 当前是否已获得「安装未知应用」授权。 */
    fun canInstall(context: Context): Boolean = context.packageManager.canRequestPackageInstalls()

    /** 跳转系统「允许安装未知应用」开关页，开完回来再点一次「安装更新」。 */
    fun requestPermissionIntent(context: Context): Intent =
        Intent("android.settings.MANAGE_UNKNOWN_APP_SOURCES").apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

    /** 唤起系统安装器。要求已获得授权，否则系统会直接忽略该请求。 */
    fun installIntent(context: Context, apk: File): Intent {
        val uri = FileProvider.getUriForFile(context, context.packageName + AUTHORITY_SUFFIX, apk)
        return Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
    }
}
