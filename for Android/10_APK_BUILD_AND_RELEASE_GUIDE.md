# Android APK 构建、签名和源码分发

当前默认 APK 为 Kotlin/WebView + Chaquopy Python 3.12。Gradle 自动打包当前 Python/Web 源码并编译 llama.cpp JNI；工具链启动器需要从固定公共制品准备。GGUF 模型和 Alpine 工具包是用户可选下载，不进入 APK。

## 固定构建环境

| 组件 | 版本 |
|---|---|
| JDK | 17 |
| 构建 Python / 嵌入 Python | 3.12（CI 构建解释器 3.12.10） |
| Gradle Wrapper | 8.11.1 |
| Android Gradle Plugin / Kotlin | 8.6.0 / 2.0.0 |
| Chaquopy | 17.0.0 |
| Android compile/target SDK | 35，min SDK 26 |
| Build Tools | 35.0.0 |
| NDK / CMake | 27.3.13750724 / 3.22.1 |
| CPU ABI | arm64-v8a、x86_64 |

Gradle distribution SHA256 为 `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6`；wrapper JAR SHA256 为 `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`，与 Gradle 官方校验文件一致。仓库包含标准 `gradlew`、`gradlew.bat`、wrapper JAR 和来源摘要清单。不能使用机器上碰巧安装的不同 Gradle 版本替代 wrapper。

SDK 管理器安装命令：

```sh
sdkmanager "platforms;android-35" "build-tools;35.0.0" "ndk;27.3.13750724" "cmake;3.22.1"
```

`ANDROID_HOME` 指向 SDK，`JAVA_HOME` 指向 JDK 17。Python 构建解释器可通过 `AGENT_WORKSPACE_BUILD_PYTHON` 指定绝对路径；不要提交包含个人 SDK 路径的 `local.properties`。

## 准备和构建

在仓库根目录安装固定 Python 依赖并准备公共构建制品。以下命令不安装到手机：

```sh
uv sync --frozen --python 3.12.10
uv run --frozen python "for Android/build_release.py" --prepare-only
```

`--prepare-only` 校验 wrapper，下载/验证 PRoot 与支持库、四份对应源码/recipe 归档，以及固定 llama.cpp 源码；同时校验/复制 llama.cpp、nlohmann 和 Chaquopy 的完整许可，再按 `--runtime chaquopy` 打包源码和 Web 资源。它不下载模型权重、不运行 Gradle、不接触手机数据。下载缓存位于忽略的 `kotlin_app/build/`，每次复用仍检查摘要。

GNU 官方 GPL v3 完整文本随源码保存为 `licenses/GPL-3.0.txt`，准备脚本先严格校验 35,149 字节和固定 SHA256，再复制到 APK；该许可证的准备不需要网络。文件存在但被修改时立即停止，只有源文件缺失时才保留从 GNU 官方 URL 下载并校验的路径。其他构建依赖仍从固定公共来源取得。

工具链的三个 gzip 对应源码归档在 APK 资产中命名为 `.tgz`，保留官方归档的压缩字节与摘要。Android 的资源合并会自动展开 `.gz` 文件，因此发布核验应读取实际 APK 中 `assets/toolchain/launchers.json`，逐项检查它声明的源码文件、大小和 SHA256。

使用 Linux/macOS shell 编译：

```sh
cd "for Android/kotlin_app"
chmod +x gradlew
./gradlew assembleDebug --no-daemon
```

PowerShell 编译：

```powershell
Set-Location 'for Android/kotlin_app'
.\gradlew.bat assembleDebug --no-daemon
```

产物为 `build/outputs/apk/debug/AgentWorkspaceMobile-debug.apk`。修改界面图标或 Markdown 渲染依赖时，先运行 `npm ci --prefix "for Android" --ignore-scripts` 和 `npm --prefix "for Android" run build:vendor` 重新生成 `web_companion/static/mobile-vendor.js`。

## Release 签名

从仓库根目录运行 `uv run --frozen python "for Android/build_release.py"` 生成 unsigned release。签名必须显式使用 `--signed` 并完整设置：

| 环境变量 | 内容 |
|---|---|
| `AGENT_ANDROID_KEYSTORE` | 私有 release keystore 文件路径 |
| `AGENT_ANDROID_KEY_ALIAS` | key alias |
| `AGENT_ANDROID_STORE_PASSWORD` | store 密码 |
| `AGENT_ANDROID_KEY_PASSWORD` | key 密码 |

缺少变量或没有显式选择 `--signed` 都会停止，不把签名凭据放入命令参数/源码/导出包。此流程不生成、不替换、不上传用户的 debug keystore。签名证书决定覆盖升级的兼容性；第一次选择 release 身份前记录证书摘要并妥善保管。使用 `apksigner verify --print-certs APK` 检查产物，保留当前已安装身份；签名不同不能覆盖安装，不能通过卸载解决。

`.github/workflows/android.yml` 在 Android/共享源码变更时跑 Python、Web、JNI/APK 构建。手动 `signed_release` 选项读取 GitHub secrets `AGENT_ANDROID_KEYSTORE_BASE64` 和后三个签名字段，将临时 keystore 写入 runner 临时目录并在结束时删除，只上传 APK 构建工件，不公开发布到商店。fork PR 不读取 release secrets。

## 设备验证和覆盖升级

用户授权且已正常解锁的设备上，保持原 applicationId/签名进行 `adb install -r APK`。不要卸载、清除数据或运行可能替换已有应用生命周期的自动安装任务。原生测试应先覆盖安装匹配签名的测试 APK，再通过 `am instrument` 指定已审阅的测试类；常规测试明确排除 `PrivateProviderRecoveryTest`。恢复测试记录临时系统设置，并在结束时恢复无障碍/电池优化/ADB forward 等改变。

CI 的可选 `emulator_smoke` 在一次性 API35 x86_64 模拟器上运行 SQLite FTS5、PRoot 启动和 Qwen 请求边界/卸载子集；未下载模型，因此不能当作实测推理或 UI 自动化成功率。实际设备验收另外记录离线生成、工具安装后的真实探测、重放/错误/重启、布局、系统版本和 OEM 限制。安全锁屏与 OEM 冻结不是测试“已通过”的替代条件。

## 清洁源码包

不直接压缩整个工作目录。生成带每文件 SHA256 的明确源码包：

```sh
python "for Android/export_android_source.py" --output artifacts/android-public-source.zip
```

导出包含当前 Android/共享 Python 源码、固定构建配置、标准 wrapper、许可说明，以及用于安装移动 Web 构建与测试依赖的 `for Android/package.json` / `package-lock.json`（与桌面端 `desktop/` 完全独立）。它排除 `.env`、凭据、数据库、设备备份、个人 SDK 路径、签名、GGUF、构建输出、JNI 下载资产和依赖缓存。导出还包含未提交的当前源码，发布前应审阅文件清单 `ANDROID_SOURCE_MANIFEST.json` 和内容。

解压到新的目录后按本页固定环境重新运行准备、测试、wrapper 构建；完整许可证从随附源码校验并复制，其他生成依赖从固定 URL 和摘要重新取得，不依赖开发机器的 `output/` 缓存。实际编译验证通过后才能声称源码包可重建。分发 APK 时同时提供本项目 Apache-2.0 许可、第三方 notices、打包的对应源代码及重建/单点二进制修改说明，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
