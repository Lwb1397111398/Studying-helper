# Android 应用自更新模块总览

## 模块职责（一句话）

让手机 App 自己发现新版本、下载安装包并唤起系统安装，配合 GitHub Actions 云端发版，实现「推代码 → 云端出包 → App 弹窗升级」的闭环，彻底告别手工传 APK。

## 运作流程（按数据真实流向）

### ① 云端出包（GitHub Actions）

1. 触发：每次 push 到 `codex/stability-convergence`（当前默认分支）或 `main`，也可在 GitHub 网页手动触发（workflow_dispatch）。
2. 构建：`.github/workflows/build-release.yml` 在 ubuntu-latest 上 checkout 全量历史（`fetch-depth: 0`，版本号依赖提交数），装 temurin JDK 17，跑 `./gradlew :app:assembleRelease --no-daemon`。
3. 版本号：构建脚本 `android/app/build.gradle` 里 `git rev-list --count HEAD` 算出提交数，作为 `versionCode`，`versionName` 形如 `1.0.21`。同一提交在任何机器算出同一个号。
4. 发布：构造 Release 说明 `notes.md`（第一行是元数据注释 `<!-- appupdate versionCode=21 versionName=1.0.21 -->`，GitHub 页面渲染不可见；后面跟最近 5 条提交标题），然后 `gh release view latest` 判断：已存在就 `gh release upload latest --clobber` 覆盖 APK 并 `gh release edit` 换说明；不存在就 `gh release create latest`。永远只有一个叫 `latest` 的 Release，APK 资产名固定 `app-release.apk`。

### ② App 检查更新（UpdateChecker）

1. 来源：`GET https://api.github.com/repos/Lwb1397111398/Studying-helper/releases/latest`（仓库公开，零配置；必须带 `User-Agent` 头，缺了 GitHub 直接 403）。
2. 解析：用 kotlinx.serialization 解析 JSON 里的 `body` 与 `assets`；再从 body 第一行正则抓 `versionCode` / `versionName`（`UpdateMeta.parse`），在 assets 里找第一个 `.apk` 拿下载地址和字节数。
3. 比较：远端 versionCode > 本地 versionCode（`PackageManager.longVersionCode`，即构建时写入的提交数）才算有更新。
4. 错误文案全人话：404 →「还没有发布过任何版本」；401 → 令牌无效；403 → 限流；IOException → 网络连接失败。

### ③ 触发时机（UpdateViewModel）

- 启动静默检查：进书籍页（BooksScreen）时 `maybeAutoCheck()`，用 SharedPreferences 记录上次成功联网检查时间，不足 24 小时跳过；失败静默不打扰。
- 手动检查：书籍页「同步与设置」分组里的「⬆️ 检查更新」按钮，不节流，成功失败都弹窗展示。

### ④ 下载（UpdateDownloader）

1. 流式下载 Release 里的 APK 到 `cacheDir/updates/update-<versionCode>.apk`，64KB 缓冲，边下边回调进度百分比给弹窗。
2. 防半截包：先写 `*.part` 临时文件 → 下载完核对字节数（Release 资产声明的 size）→ 一致才改名正式文件；任何异常都删掉 .part。
3. 省流量：本地已有同版本完整文件（长度一致）直接复用，不重新下载。

### ⑤ 安装（UpdateInstaller）

1. FileProvider（authority 为 `com.studyinghelper.mobile.update`，只开放缓存目录 `updates/` 子路径）把 APK 转成 content:// URI。
2. `ACTION_INSTALL_PACKAGE` + 读权限标志唤起系统安装器。
3. 缺「安装未知应用」授权时：弹窗引导 → `ACTION_MANAGE_UNKNOWN_APP_SOURCES` 跳系统开关页 → 用户开完回来再点一次「安装更新」。

## 入口文件清单

| 文件 | 内容 |
| --- | --- |
| `android/app/src/main/java/com/studyinghelper/mobile/data/update/UpdateModels.kt` | RemoteRelease / UpdateCheckResult / 元数据解析 UpdateMeta |
| `.../data/update/UpdateChecker.kt` | GitHub Release 检查（纯 JVM，baseUrl 可注入） |
| `.../data/update/UpdateDownloader.kt` | 下载（纯 JVM 核心 + Android 落盘路径） |
| `.../data/update/UpdateInstaller.kt` | FileProvider + 安装/授权 Intent |
| `.../ui/UpdateViewModel.kt` | 状态机（Idle/Checking/Available/Downloading/Downloaded/NeedInstallPermission/Failed）+ 24h 节流 |
| `.../ui/UpdateDialog.kt` | 更新弹窗 Compose UI |
| `android/app/src/main/AndroidManifest.xml` | `REQUEST_INSTALL_PACKAGES` 权限 + FileProvider 注册 |
| `android/app/src/main/res/xml/file_paths.xml` | FileProvider 只开放 `updates/` |
| `android/app/build.gradle` | versionCode=提交数、debug/release 统一签名 |
| `android/keystore/app.keystore` | 统一签名钥匙（本机调试钥匙副本，口令 android / 别名 androiddebugkey） |
| `.github/workflows/build-release.yml` | CI 构建发版 |
| `android/app/src/test/java/com/studyinghelper/mobile/data/update/` | 单测（FakeHttpServer 手写 ServerSocket 假 GitHub） |

## 对外接口 / 被谁调用

- BooksScreen 调 `UpdateViewModel`：`maybeAutoCheck()` / `manualCheck()` / `download()` / `install()` / `openInstallPermissionSettings()` / `dismiss()`。
- CI 产物（latest Release 的元数据注释 + app-release.apk）是检查与下载的数据源。

## 依赖的上游模块

- 无业务上游（不依赖 Room/同步/教学）。依赖 AndroidX core（FileProvider）、kotlinx-serialization（解析 GitHub JSON）、Compose Material3（弹窗）。

## 关键数据结构

- `RemoteRelease`：versionCode、versionName、apkUrl、apkSize、releaseNotes、htmlUrl。
- `UpdateCheckResult`：UpdateAvailable / UpToDate / Failed 三态。
- `UpdateUiState`：Idle → Checking → Available → Downloading(progress) → Downloaded →（NeedInstallPermission）→ Idle。
- Release 说明元数据：`<!-- appupdate versionCode=N versionName=1.0.N -->`（必须第一行，CI 生成）。

## 已知坑与约束

- **签名一致性**：debug 与 release 都锁 `android/keystore/app.keystore`（本机调试钥匙副本）。钥匙随公开仓库可见，口令是标准 android 调试口令——签名一致不授予任何安装/数据权限，个人项目风险可控；换正式签名需全量重装。
- **providers.exec 的 Groovy 两个坑（实战踩过）**：① 闭包里不能直接引用 `rootDir`，会被解析到 exec 配置对象上抛 MissingPropertyException，须先存局部变量；② 输出取值用 `.standardOutput.asText.get()`，Gradle 8.9 没有 `.text`。两个错都被 try/catch 吞成 versionCode=1，查构建日志里的「无法统计 git 提交数」告警可定位。
- **本机跑 Gradle 建议 --no-daemon**：默认守护进程模式曾因整机内存耗尽 JVM 崩溃（hs_err_pid*.log），表现为构建僵死无输出；日志经 PowerShell 重定向是 UTF-16LE 编码，grep 前先 iconv。
- **CI 必须 fetch-depth: 0**：shallow clone 数错提交数，版本号对不上。
- **gradlew 执行位**：Windows 提交默认 100644，CI Linux 报 Permission denied；已用 `git update-index --chmod=+x` 修为 100755。
- **AGP 单测禁用 com.sun.net.httpserver**：假 GitHub 用手写 ServerSocket（`FakeHttpServer.kt`），别换 httpserver。
- **versionCode 只增不减**：覆盖安装要求新包 versionCode ≥ 已装版本；删提交会导致版本号回退，装不上。
- **测试假发布的号要 ≥ 已装版本**，否则安装被系统拒。
- 该仓库为公开仓库：更新链路零令牌可用；若未来转私有，需按 GitHub 细粒度令牌方案补 Authorization。

## 最后更新

- 2026-10-05：模块首次落地——统一签名、版本号=提交数、检查/下载/安装全链路、CI 发版工作流、单测（假 GitHub），并新建本总览。
