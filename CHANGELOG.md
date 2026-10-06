# Changelog

## 1.0.1 — 2026-10-06

修复与改进版。Fixes and improvements.

### 中文

**修复**
- 模型拒收图片（如 DeepSeek 返回「unsupported image」400）后，对话不再每次重试、继续都报同样的错：被拒的图片会自动从后续请求中移除并告知模型，任务继续执行。
- `attach_image` 在附加前检查图片结构（PNG 校验和、JPEG 帧、GIF/WebP 完整性），截断或伪造的图片不会再被发给模型。
- 启动卡在「正在等待本地服务凭据」：应用改为按引擎的启动进度判断是否卡死，正常的慢启动（更新后首次解压、任务较多）不会再被误杀重启；真正卡住时才重启引擎，并在加载页显示当前进行到哪一步。
- 引擎启动的每一步与启动卡住时的线程堆栈都会写入日志，便于定位。
- 修复诊断日志分享后接收方可能无法打开文件的问题。
- 界面：任务失败时不再同时出现提示条和错误卡片两份相同的错误；玻璃输入框、顶栏和任务状态条加强了磨砂与底色，背后滚动的文字不再与按钮文字混在一起；过长的错误提示可滚动，不会挡住输入框。

**新增**
- 加载页右上角新增「导出日志」与「检查更新」（与「模型设置」并排），进不去应用也能用。导出日志可分享文件、保存到手机，或一键打开 GitHub 新建 Issue 页面并预填脱敏后的启动日志摘要（需登录 GitHub，由你确认后提交）。
- 应用内更新（OTA）：每天自动检查 GitHub 是否有新版本（可在「设备与工具 → 版本与更新」关闭），也可手动检查；下载后校验 SHA-256、包名与签名，再交给系统安装器由你确认安装。首次安装更新时需按提示允许「安装未知应用」。

**升级说明**
- 从 1.0.0 直接覆盖安装即可，数据保留。从 1.0.1 起，之后的版本可在应用内更新。

### English

**Fixes**
- After a provider rejects an image (for example DeepSeek's "unsupported image" 400), the conversation no longer fails the same way on every retry or continue: the rejected image is dropped from later requests, the model is told, and the task goes on.
- `attach_image` checks the image structure first (PNG checksums, JPEG frames, GIF/WebP integrity), so truncated or fake images are never sent to the model.
- Stuck at "Waiting for the local service credentials": the app now judges a stuck engine by its start-up progress, so a slow but healthy start (first start after an update, a long task history) is no longer killed and restarted; only a start with no progress is restarted, and the loading screen shows the current step.
- Every engine start-up step, and the thread stacks of a stalled start, are written to the logs.
- Fixed shared diagnostics files that the receiving app could not open.
- Interface: a failed task no longer shows the same error twice (notice bar and error card); the glass composer, header and task status pill have more frost and tint so text scrolling behind them no longer mixes with their labels; long error notices scroll instead of covering the composer.

**New**
- "Export logs" and "Updates" on the loading screen next to "Model settings", usable even when the app cannot get past start-up. Export can share the file, save it to the phone, or open a new GitHub issue prefilled with a masked start-up log summary (you sign in to GitHub and submit it yourself).
- In-app updates (OTA): a daily check for a new GitHub release (can be turned off under Device & tools → Version and updates) and a manual check; the download is verified (SHA-256, package name and signature) before Android's installer asks you to confirm. The first update asks you to allow installing unknown apps.

**Upgrading**
- Install over 1.0.0; data is kept. From 1.0.1 on, later versions can be installed from inside the app.

## 1.0.0 — 2026-10-05

首个正式版。First stable release.

### 中文

**核心能力**
- 在手机上执行多步骤 Agent 任务：流式回复、思考过程、工具调用状态实时可见；敏感操作前审批；三种执行模式（仅工作区 / YOLO / 完全访问）。
- 云端模型（OpenAI 兼容接口、Anthropic、Gemini、Ollama）与本机离线模型（Qwen3 / Qwen3.5 GGUF，经 llama.cpp 在 CPU 上运行，Qwen3.5 支持图片）。
- 工作区与文件：生成文件可打开、预览、分享、另存；文本文件可编辑；系统文件选择器中可见。
- 从其他应用分享文件进对话；PDF 按页读取与扫描页 OCR。
- 定时任务、可回放工作流、任务评测、跨设备接力；可选 Alpine 开发工具链；可选无障碍手机操作。

**本版新增与改进**
- 任务中途插话：任务执行时输入的内容加入当前任务，Agent 在下一步采纳。
- 全新界面：会话列表抽屉、输入区内的模型与权限芯片、常用快捷任务（总结要点、翻译润色、做个网页、分析数据）、会话自动命名与归档、工作区移除。
- 液态玻璃风格：真实边缘折射、色散与角落高光；二级菜单与回复同样为玻璃；十二种背景与自定义壁纸；五种主题色、浅色 / 深色、动画可调。
- 中文 / English 界面，默认跟随系统。
- 流畅度：在骁龙 888 上滚动从 23 帧提升到约 90 帧；玻璃贴图内存约 230 KB。
- 可靠性：引擎停止或重启后自动恢复连接并重新载入页面；修复启动中被误重启导致的「Failed to fetch」与卡在「确认本地服务身份」；引擎请求出错时返回明确错误；引擎卡住时记录线程堆栈。
- 「设备与工具」页可一键分享诊断日志，引擎令牌与 API 密钥自动隐藏。
- 安全：引擎在交出访问令牌前向应用证明身份；确认框改为应用内对话框；禁止双指缩放页面。

**升级说明**
- 这是第一个使用正式签名的版本。若手机上装过 1.0.0 之前的测试版，需要先卸载再安装（签名不同无法覆盖），测试版的数据不会保留。

### English

**Core**
- Multi-step agent tasks on the phone: streamed replies, visible reasoning and live tool-call status; approval before sensitive actions; three execution modes (workspace / YOLO / full access).
- Cloud models (OpenAI-compatible APIs, Anthropic, Gemini, Ollama) and offline on-device models (Qwen3 / Qwen3.5 GGUF on the CPU through llama.cpp, with image input on Qwen3.5).
- Workspaces and files: open, preview, share or save generated files; edit text files; workspaces appear in the system file picker.
- Share files into a conversation from other apps; page-by-page PDF reading with OCR for scanned pages.
- Scheduled tasks, replayable workflows, task evaluations, device hand-off; optional Alpine developer toolchain; optional accessibility-based phone control.

**New and improved in this release**
- Add to a running task: anything typed while a task runs joins it and is taken into account at the next step.
- Redesigned interface: session drawer, model and permission chips in the composer, everyday shortcuts (summarize, translate, make a web page, analyze data), automatic session titles, archiving and workspace removal.
- Liquid-glass style: real edge refraction, colour dispersion and corner highlights; menus and replies are glass too; twelve backgrounds or a custom wallpaper; five accent colours, light/dark themes and adjustable motion.
- Chinese / English interface, following the system language by default.
- Performance: scrolling went from 23 fps to about 90 fps on a Snapdragon 888; glass maps use about 230 KB.
- Reliability: the app revives the engine and reloads the page after the engine stops or restarts; fixed an engine restart during start-up that caused "Failed to fetch" and a hang at "Verifying the local service"; request errors come back as clear messages; a stalled engine records its thread stacks.
- Device & tools can share a diagnostics file, with the engine token and API keys masked.
- Security: the engine proves its identity before the app hands over its access token; confirmation dialogs are native app dialogs; pinch-zoom is disabled.

**Upgrading**
- This is the first release with the production signing key. If a pre-1.0.0 test build is installed, uninstall it first (a different signature cannot be upgraded in place); test-build data is not kept.
