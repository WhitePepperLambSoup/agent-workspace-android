# 独立 APK：WebView、Chaquopy 与可选 PRoot 工具链

本页替代早期“APK 内置完整 Termux rootfs”提案。实际默认构建使用 Chaquopy Python 3.12，在 APK 的 Android 原生进程内调用共享 Agent 引擎；首次运行提取的是 Agent 源码和 Web 资源，不是自动安装全部 Termux 工具。`TermuxDaemonService` 是保留的组件名称，不能据名称推断其当前执行模式。

APK 包含 Kotlin 界面/通知/前台服务、SQLite FTS5 桥、无障碍动作桥、llama.cpp CPU JNI，以及固定的 PRoot 启动器。小模型 GGUF 和 Alpine 开发工具包由用户在二级菜单选择下载；安装/验证/实际探测结果决定是否可用。

Android 10 起对应用可写目录的可执行文件有系统限制。工程保持 SDK 35，使用 `nativeLibraryDir` 中随 APK 安装的 lib*.so 启动器和 PRoot loader 执行下载的工具环境，未采用 targetSdk 28 的旧规避方案。PRoot 作为独立进程运行，原始和修改后二进制摘要、对应源代码、许可证以及重建方法随启动器资产提供。

WebView 连接应用私有本地 gateway，模型凭据保留在按来源隔离的 Keystore 存储。模型、工具、定时、工作流和诊断入口位于二级菜单。升级保持签名和 applicationId；不要为“修复启动”卸载、清除数据或替换用户的 debug 密钥。

前台通知、WorkManager 和恢复状态帮助任务跨 UI 重建和进程重启恢复，但操作系统仍可冻结/杀死进程，安全锁屏会阻断 UI 动作。中断动作的 unknown 执行结果需要人工检查，不能自动补跑。更多细节见 [当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md)。
