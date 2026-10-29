# AnimeTracker

本地动漫记录工具。

已关联 Bangumi ID 的动漫档案提供“在 Kazumi 打开”：设备安装了支持 `kazumi://bangumi/<id>` 的 Kazumi 后，点击即可打开同一部番剧。这个链接只负责跳转，不读取或同步 Kazumi 的观看进度。


本包是**跨平台 App 源码**，不是已经签名的安装包。界面已简化；桌面入口改为 Tauri 独立窗口，不再调用终端或 Safari。运行时打包在应用内部，安装成品后不需要 Python、Node.js 或本地服务器。

| 平台 | 本版提供 | 仍需完成 |
| --- | --- | --- |
| macOS | Tauri 工程、AT 图标、构建脚本、Apple Silicon / Intel 构建流程 | 在 Mac 构建、真机验证；公开分发的签名/公证 |
| Windows | 同一工程、无控制台入口、x64 安装包构建流程 | Windows 构建和真机验证；公开分发签名 |
| iOS / iPadOS | 共用界面、WASM 数据层、Tauri mobile 入口、隐私清单 | 生成 Xcode 工程、签名、真机验证；TestFlight / App Store 发布 |
| Android | 共用界面、WASM 数据层、Tauri mobile 入口 | Android 工具链、生成工程、签名和真机验证 |
| 浏览器 | 静态构建，IndexedDB 本地存储 | HTTPS 部署后按设备验证离线缓存及存储限制 |

构建最低目标设为 macOS 13.3 / iOS 16.4；仍需真机验证兼容性。

原生安装包尚未在本次环境中生成；不能把“有共同源码”当作“所有设备已经测试通过”。手机与桌面上的数据目前各自独立，**同步尚未实现**。

## 先保留旧记录

1. 在旧版“数据”页导出 **完整 JSON**，另存一份 `.db` 备份。
2. 新版首次打开是空资料库；在“数据 → 导入 JSON”选择完整 JSON。ID、日期、来源与观看轮次都会保留。
3. 核对条目数量及观看记录后再决定是否删除旧程序。不要只导出“动漫清单 CSV”，它不包含完整观看记录。

新版不会直接改写旧版 `~/Library/Application Support/AnimeTracker/anime_tracker.db`。旧 `.db` 也可通过“从备份恢复”迁移，但会替换新版当前资料库，操作前会自动备份。

## 网页版：推荐先用这个

项目含完整静态网页和离线资源。将源码提交到 GitHub 后，打开 **Settings → Pages → Build and deployment → Source: GitHub Actions**，再到 **Actions → Publish web app → Run workflow**。成功后 Pages 地址通常是 `https://用户名.github.io/仓库名/`。使用 HTTPS 打开一次并等待离线资源下载完成，就可以离线使用；iPhone Safari 的分享菜单选择“添加到主屏幕”，Mac / Windows 可用浏览器的“安装应用”功能。无需 iOS 签名，日常不用打开终端。

### 网页本地版

这就是上述网站安装后的模式：界面和运行时由浏览器缓存，个人记录存于当前设备的 IndexedDB；离线打开仍可使用。初次安装及版本更新需要联网。请不要清理该网站的数据或卸载浏览器，除非已在“数据”页导出完整 JSON 备份。它不会自动同步至另一台设备。

如需下载可自行托管的静态文件，在 GitHub **Actions → Package offline web app → Run workflow**，从 Artifacts 下载 `AnimeTracker-Web-Local`。这些文件必须由 HTTPS 站点或本机 HTTP 服务提供，不能双击 `index.html` 运行；直接访问现有 Pages 站点并安装到主屏幕更省事。

**这个版本没有账号登录或跨设备同步。** 网页版的数据保存在当前浏览器的 IndexedDB；换手机、浏览器、清理网站数据，记录不会自动出现。要迁移，在旧设备“数据 → 完整 JSON”导出，在新设备导入。定期保存一份 `.db` 备份。公共 GitHub Pages 只托管程序文件，**不要上传个人 JSON、数据库或 WebDAV 密码**。未来可直接用 InfiniCLOUD WebDAV 同步原生 App；已实测当前 InfiniCLOUD WebDAV 未许可 GitHub Pages 跨域直连，纯网页版同步需要代理或其他同源服务。详见 `docs/SYNC.md`。

本地查看网页版开发预览：`npm ci` 后 `npm run dev`，打开 `http://127.0.0.1:1420`。初次安装依赖和发布需要终端；日常访问网站不需要。

## 获得电脑 App：GitHub 构建

1. 将本文件夹的**内容**提交到 GitHub 仓库根目录，包含 `.github/workflows/build-apps.yml`、`src-tauri` 和 `package-lock.json`。
2. 打开仓库 **Actions → Build desktop apps → Run workflow**。
3. 构建成功后，在任务底部 **Artifacts** 下载对应系统的包并解压。
4. Apple Silicon Mac 选择 `macOS-Apple-Silicon`，Intel Mac 选择 `macOS-Intel`：打开 `.dmg`，把 AnimeTracker 拖入“应用程序”。Windows 选择 `Windows-x64`，运行安装程序。
5. 以后从“应用程序”、Dock 或开始菜单启动，不会打开终端。

该流程只生成构建产物，不自动发布 Release，也没有配置开发者签名。公开分发前请按 Tauri 官方文档配置 macOS 签名/公证或 Windows 签名，并在目标设备验证。不要将证书、密码、个人数据库提交到仓库。

## 在自己的 Mac 构建

安装 Node.js 24、Rust stable（至少 1.90）及 Xcode/命令行工具，按照 [Tauri 前置要求](https://v2.tauri.app/start/prerequisites/) 配置环境。然后双击 `Create-Mac-App.command`。

也可以在项目目录运行：

```sh
npm ci
npm run app:build
```

构建时需要终端和网络，日常启动成品 App 不需要。输出在 `src-tauri/target/release/bundle/`。将 `macos/AnimeTracker.app` 拖进“应用程序”。旧 `Start-AnimeTracker.command` 仅保留给旧版 Python 服务调试，仍会打开终端，不是新版 App 的启动入口。

Windows 使用同样的 npm 命令，构建环境还需 Microsoft C++ Build Tools 和 WebView2，具体见官方前置要求。

## iPhone / iPad

iOS 的构建与签名在 Mac + Xcode 上完成。项目提供 `scripts/build_ios_ipa.sh`，运行前先在 Xcode 登录 Apple ID，设置 Signing Team，并确认 `io.animetracker.app` 这个 Bundle ID 可由你的团队使用（否则先改为自己的唯一 ID）：

```sh
sh scripts/build_ios_ipa.sh
```

脚本将安装依赖、初始化 iOS 工程并尝试以 `debugging` 导出 IPA，完成后打印 `.ipa` 路径。首次生成工程后，请在 Xcode 检查签名设置，并将 `src-tauri/PrivacyInfo.xcprivacy` 加入应用 target；然后重跑脚本。需要 TestFlight / App Store 构建时，在完成相应证书和描述文件配置后使用 `IOS_EXPORT_METHOD=release-testing` 或 `app-store-connect`。可手动执行：

```sh
npm run tauri -- ios dev
npm run tauri -- ios build --export-method debugging
```

iOS 不能直接安装 Mac `.app` 或 Windows `.exe`。本仓库尚无 Apple 签名身份，因而不包含已签名、可安装的 IPA；构建脚本须在 Mac 执行，并经真机验证。Ad Hoc 分发需注册设备并使用相应描述文件。Android 安装 SDK/NDK 后使用 `npm run tauri -- android init` / `android dev` / `android build`，同样需要真机验证。

## 开发与测试

```sh
npm ci
npm run test:portable
npm run build
npm run app:dev
```

`npm run dev` 只启动浏览器开发预览。`dist/` 是可部署的静态文件，并带离线资源缓存；不能通过双击 `index.html` 运行。浏览器存储和安装版 App 存储相互独立，卸载或清理浏览器数据前请导出备份。iOS 浏览器可能回收未使用的网站数据，离线缓存不能替代资料备份。

结构：

- `local_app/store.py`：SQLite 数据模型；保留旧版导入、合并和校验规则。
- `portable/`：WASM Python worker、界面桥接和持久化适配器。全部运行资源本地打包，没有运行时 CDN。
- `src-tauri/`：原生窗口、文件选择、原子保存；存储文件位于系统应用资料目录的 `io.animetracker.app` 目录（iOS 位于沙盒）。
- `hive_exporter/`：独立 Kazumi 导出工具。先关闭 Kazumi，再用 `Export-Kazumi.command` 从临时副本导出。
- `docs/SYNC.md`：后续 WebDAV 同步设计；不会写入 Kazumi 的同步目录。
- `.github/workflows/build-apps.yml`：手动触发的桌面安装包构建。

原生数据使用 `storage.json` 容器保存 SQLite 与恢复前备份。只允许固定数据库/备份名；持久化失败会回滚内存更改；并发旧窗口写入会被拒绝，需重新打开。备份累积后容器有 512 MiB 上限；本版没有自动清理备份。导出文件不加密。

已关联 Bangumi 的动漫会保存封面地址，书架默认加载远程封面；可在书架关闭“加载远程封面”。当前版本无云同步、统计上报或用户账号。
