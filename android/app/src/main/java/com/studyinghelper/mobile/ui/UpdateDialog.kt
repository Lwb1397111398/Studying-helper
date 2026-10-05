package com.studyinghelper.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.studyinghelper.mobile.data.update.RemoteRelease

/**
 * 更新弹窗：发现新版本 → 下载进度 → 安装 → 补授权，全流程在同一弹窗里推进。
 */
@Composable
fun UpdateDialog(state: UpdateUiState, viewModel: UpdateViewModel) {
    when (state) {
        is UpdateUiState.Available -> AvailableDialog(state.release, viewModel)
        is UpdateUiState.Downloading -> DownloadingDialog(state.release, state.progress)
        is UpdateUiState.Downloaded -> DownloadedDialog(state.release, viewModel)
        is UpdateUiState.NeedInstallPermission -> PermissionDialog(state.release, viewModel)
        is UpdateUiState.UpToDate -> MessageDialog(
            title = "已是最新版本",
            message = "当前没有可用的更新。",
            onDismiss = { viewModel.dismiss() },
        )
        is UpdateUiState.Failed -> MessageDialog(
            title = "检查更新失败",
            message = state.message,
            onDismiss = { viewModel.dismiss() },
        )
        UpdateUiState.Checking, UpdateUiState.Idle -> Unit
    }
}

@Composable
private fun AvailableDialog(release: RemoteRelease, viewModel: UpdateViewModel) {
    AlertDialog(
        onDismissRequest = { viewModel.dismiss() },
        title = { Text("发现新版本 ${release.versionName}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (release.releaseNotes.isNotBlank()) {
                    Text(
                        release.releaseNotes,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                Text(
                    "安装包约 ${formatSize(release.apkSize)}，建议在 Wi-Fi 下下载。",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        },
        confirmButton = { TextButton(onClick = { viewModel.download(release) }) { Text("下载更新") } },
        dismissButton = { TextButton(onClick = { viewModel.dismiss() }) { Text("以后再说") } },
    )
}

@Composable
private fun DownloadingDialog(release: RemoteRelease, progress: Int) {
    AlertDialog(
        onDismissRequest = {},
        title = { Text("正在下载 ${release.versionName}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                LinearProgressIndicator(
                    progress = { progress / 100f },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "$progress%",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        },
        confirmButton = {},
        dismissButton = {},
    )
}

@Composable
private fun DownloadedDialog(release: RemoteRelease, viewModel: UpdateViewModel) {
    AlertDialog(
        onDismissRequest = { viewModel.dismiss() },
        title = { Text("下载完成") },
        text = { Text("新版本 ${release.versionName} 已就绪，点击安装后按系统提示完成升级。") },
        confirmButton = { TextButton(onClick = { viewModel.install(release) }) { Text("安装更新") } },
        dismissButton = { TextButton(onClick = { viewModel.dismiss() }) { Text("稍后") } },
    )
}

@Composable
private fun PermissionDialog(release: RemoteRelease, viewModel: UpdateViewModel) {
    AlertDialog(
        onDismissRequest = { viewModel.dismiss() },
        title = { Text("需要授权安装") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("安装更新需要允许「安装未知应用」权限：先点下面的「去授权」，在系统设置里打开开关后回来，再点「安装更新」。")
                TextButton(onClick = { viewModel.openInstallPermissionSettings() }) {
                    Text("去授权")
                }
            }
        },
        confirmButton = { TextButton(onClick = { viewModel.install(release) }) { Text("安装更新") } },
        dismissButton = { TextButton(onClick = { viewModel.dismiss() }) { Text("取消") } },
    )
}

@Composable
private fun MessageDialog(title: String, message: String, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = onDismiss) { Text("知道了") } },
    )
}

private fun formatSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> "${(bytes + 1024 * 1024 / 2) / (1024 * 1024)} MB"
    bytes >= 1024 -> "${(bytes + 1024 / 2) / 1024} KB"
    else -> "$bytes B"
}
