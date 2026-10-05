package com.studyinghelper.mobile.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.studyinghelper.mobile.data.update.RemoteRelease
import com.studyinghelper.mobile.data.update.UpdateCheckResult
import com.studyinghelper.mobile.data.update.UpdateChecker
import com.studyinghelper.mobile.data.update.UpdateDownloader
import com.studyinghelper.mobile.data.update.UpdateInstaller
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

sealed class UpdateUiState {
    data object Idle : UpdateUiState()
    data object Checking : UpdateUiState()
    data class Available(val release: RemoteRelease) : UpdateUiState()

    /** 手动检查发现已是最新版。 */
    data class UpToDate(val remoteVersionCode: Int) : UpdateUiState()

    data class Downloading(val release: RemoteRelease, val progress: Int) : UpdateUiState()
    data class Downloaded(val release: RemoteRelease, val apk: File) : UpdateUiState()

    /** 缺「安装未知应用」授权，用户去开完回来点「安装更新」继续。 */
    data class NeedInstallPermission(val release: RemoteRelease) : UpdateUiState()

    data class Failed(val message: String, val fromAutoCheck: Boolean) : UpdateUiState()
}

/**
 * 应用自更新：启动 24h 节流静默检查 + 设置页手动检查 + 下载 + 唤起安装。
 */
class UpdateViewModel(app: Application) : AndroidViewModel(app) {

    companion object {
        private const val PREFS = "app_update"
        private const val KEY_LAST_CHECK = "last_check_at_ms"
        private const val AUTO_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000L
    }

    private val checker = UpdateChecker()
    private val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private val _state = MutableStateFlow<UpdateUiState>(UpdateUiState.Idle)
    val state: StateFlow<UpdateUiState> = _state

    fun currentVersionCode(): Int = try {
        getApplication<Application>().packageManager
            .getPackageInfo(getApplication<Application>().packageName, 0)
            .longVersionCode.toInt()
    } catch (_: Exception) {
        0
    }

    /** 启动时静默检查：距上次成功联网检查不足 24 小时则跳过，失败不打扰用户。 */
    fun maybeAutoCheck() {
        if (_state.value != UpdateUiState.Idle) return
        val last = prefs.getLong(KEY_LAST_CHECK, 0L)
        if (System.currentTimeMillis() - last < AUTO_CHECK_INTERVAL_MS) return
        checkInternal(fromAuto = true)
    }

    /** 手动检查：不节流，结果（含失败）都展示。 */
    fun manualCheck() {
        if (_state.value == UpdateUiState.Checking || _state.value is UpdateUiState.Downloading) return
        checkInternal(fromAuto = false)
    }

    private fun checkInternal(fromAuto: Boolean) {
        _state.value = UpdateUiState.Checking
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) {
                checker.check(currentVersionCode())
            }
            if (result !is UpdateCheckResult.Failed) {
                prefs.edit().putLong(KEY_LAST_CHECK, System.currentTimeMillis()).apply()
            }
            _state.value = when (result) {
                is UpdateCheckResult.UpdateAvailable -> UpdateUiState.Available(result.release)
                is UpdateCheckResult.UpToDate ->
                    if (fromAuto) UpdateUiState.Idle else UpdateUiState.UpToDate(result.remoteVersionCode)
                is UpdateCheckResult.Failed ->
                    if (fromAuto) UpdateUiState.Idle else UpdateUiState.Failed(result.message, false)
            }
        }
    }

    fun download(release: RemoteRelease) {
        if (_state.value is UpdateUiState.Downloading) return
        _state.value = UpdateUiState.Downloading(release, 0)
        viewModelScope.launch {
            try {
                val apk = withContext(Dispatchers.IO) {
                    val dest = UpdateDownloader.apkFile(getApplication(), release.versionCode)
                    UpdateDownloader.download(release.apkUrl, dest, release.apkSize) { progress ->
                        _state.value = UpdateUiState.Downloading(release, progress)
                    }
                }
                _state.value = UpdateUiState.Downloaded(release, apk)
            } catch (e: Exception) {
                _state.value = UpdateUiState.Failed(e.message ?: "下载失败，请重试", false)
            }
        }
    }

    /** 点「安装更新」：有授权直接唤起安装器，没授权先引导去开。 */
    fun install(release: RemoteRelease) {
        val context = getApplication<Application>()
        val apk = UpdateDownloader.apkFile(context, release.versionCode)
        if (!apk.exists()) {
            _state.value = UpdateUiState.Failed("安装包不存在，请重新下载", false)
            return
        }
        if (!UpdateInstaller.canInstall(context)) {
            _state.value = UpdateUiState.NeedInstallPermission(release)
            return
        }
        context.startActivity(UpdateInstaller.installIntent(context, apk))
    }

    /** 点「去授权」：跳系统开关页，回来后再点「安装更新」。 */
    fun openInstallPermissionSettings() {
        getApplication<Application>().startActivity(
            UpdateInstaller.requestPermissionIntent(getApplication())
        )
    }

    fun dismiss() {
        _state.value = UpdateUiState.Idle
    }
}
