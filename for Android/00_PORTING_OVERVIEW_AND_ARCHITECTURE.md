# Android 当前架构

当前 APK 采用 Kotlin 宿主、WebView 移动界面、Chaquopy Python 3.12 和共享 Agent 核心。Android 专用适配器、管理 API 和 UI 源码位于 `for Android/`，打包时读取共享 `src/agent_workspace` 的当前源码。它不需要另装 Termux，也不包含可直接执行的桌面程序。

```text
WebView / Kotlin Activity
        ↓ 已配对的本地 Mobile Gateway
MobileRuntimeController → 持久化任务事件 / 取消 / 审批
        ↓
Chaquopy ApplicationService + 共享 Agent 核心
        ├─ 云 Provider → 按服务来源保存的 Keystore 凭据
        ├─ 嵌入式 Qwen Provider → LocalModelBridge JNI → llama.cpp CPU
        ├─ Android 动作桥 → 用户授权的 Accessibility 服务
        └─ 可选工具链 → packaged PRoot 独立进程 → 下载的 Alpine 工具
```

模型文件、工具链根目录、会话和 SQLite 状态保存在应用私有数据目录。模型使用固定 repository revision/文件/大小/SHA256；未完成或摘要不符的文件不是可用模型。GGUF 不随 APK 分发。Qwen3.5 文本与配套视觉组件分开下载；mtmd 在 CPU 上编码图片，再与文本一起交给 qwen35 架构推理。图片输入、视觉 token、内存和取消均有边界检查。

图片附件先按会话导入记录和 SHA256 验证，再与任务原子保存为私有 BinaryArtifact。controller 向共享 Agent 核心传递真实 ImagePart，排队和重启恢复不依赖原导入文件。云端沿用共享 OpenAI Chat Completions/Responses、Anthropic、Gemini 和 Ollama 图片编码，模型或服务端拒绝图片时保留明确失败。

开发工具通过 Android 原生库目录中的 PRoot 启动器运行，避免 Android 10 及以后对应用可写数据目录执行文件的限制。没有降低 targetSdk 来规避该限制。可选工具链实际探测成功后才进入能力列表；共享核心的工具审批、路径检查和私有工作区边界继续生效。

工作流重放是独立的 controller 执行回调，使用相同串行任务锁、审批代理和取消生命周期；不会把步骤转换成另一段模型目标提示。动作派发前持久化，unknown 结果禁止继续重放。测量导出区分 controller 执行记录、人工审阅记录和 24 个声明式场景。

前台服务与系统调度能够帮助恢复，不能保证在所有 OEM、Doze、锁屏和资源压力条件下持续执行。安全 keyguard 只能由用户正常解锁。具体设备/API覆盖应以实际报告为准。

详细安装、构建、签名和许可入口见 [README.md](README.md)、[10_APK_BUILD_AND_RELEASE_GUIDE.md](10_APK_BUILD_AND_RELEASE_GUIDE.md) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。其他早期 Termux 方案文档是历史替代宿主说明。
