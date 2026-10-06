# Changelog

## 1.1.0 — 2026-10-07

功能版。Feature release.

### 中文

**新增**
- 自定义快捷任务：在「界面偏好 → 编辑快捷任务」里添加、修改、排序或删除输入框上方的快捷按钮（最多 8 个），每个可选填入输入框或直接发送。
- 拍照提问：点回形针可选「拍照」或「选择文件」，照片进入附件收件箱，添加到对话即可提问。
- 公式与流程图：回复里的 LaTeX 公式（支持 `$…$`、`$$…$$`、`\(…\)`、`\[…\]`）显示为排好版的公式；`mermaid` 代码块在回复完成后画成流程图（复制按钮仍复制源码，画不出来的保留为源码）。
- 记忆：新增「记忆」页，查看、添加、修改、删除 AI 记住的关于你的信息。AI 会自动记下以后用得上的内容，但有节制：最多 30 条、每条不超过 200 字、每次任务最多自动记 3 条，相似内容不重复记，密码、密钥、验证码和证件号不会被记住；对话时只带上最新的记忆（约 2000 字以内），控制 Token 用量。可以随时关闭自动记忆或全部记忆。
- 编辑重发与重新生成：自己的消息可以复制或编辑后重新发送，最新一条回复可以重新生成，会替换之后的对话（已改动的文件不会撤销）。
- 多套模型配置：把常用的服务商与模型存成配置，一键切换。云端模型之间切换、修改模型或思考强度不再重启引擎；切换到或离开本机模型时仍会重启。API 密钥按服务商地址保存在系统密钥库，配置里不含密钥。
- 备份与恢复：把全部会话、记忆、定时任务与流程、内置工作区文件以及模型和界面设置导出为一个 zip，换手机或重装后恢复。不含 API 密钥、已下载的本机模型和开发工具链；恢复前的数据会保留一份。
- 后台服务：AI 可以启动需要一直运行的程序（本地网页服务、机器人、监听程序等），任务结束后继续运行。在新的「后台服务」页可查看输出、在浏览器中打开、停止、重启或删除，可设置「随引擎启动」；可选「息屏后继续运行」。
- 长时间命令：安装、编译等命令最长可运行 30 分钟，执行时在工具卡片里实时显示输出。此前每个工具最多运行 2 分钟。
- 全局入口：通知栏快捷开关「问 Agent」；可拖动的悬浮球，点一下开新对话，长按可截屏提问、语音提问或隐藏；长按桌面图标可直接选「新对话」「语音提问」「拍照提问」。
- 内置浏览器：AI 可以用手机自带的 WebView 打开网页，读取需要脚本渲染的页面，点击、填表、按回车和截图。打开网页、点击和填表需要你批准，读取和截取当前页面不需要；它的登录状态与应用界面分开保存，可在「设备与工具」里测试或清除。
- 通知触发：选定应用的通知到达时（可按关键词过滤），让 AI 按你写的要求处理，例如「快递短信来了就记下取件码」。默认每次运行前先通过通知问你；只读取你选定应用的通知，内容只交给被触发的任务；每条规则至少间隔 30 秒、每天最多 30 次。需要你在系统设置里授予通知使用权。

**修复**
- 修复 1.0.1 中设置页的输入框和下拉框（如模型名、工作区路径）失去样式的问题。
- 应用更新后，若引擎在你打开应用前已被后台恢复任务启动，会继续运行更新前的代码，界面停留在旧版本。现在打开应用时检测到更新会重启引擎。

**升级说明**
- 从 1.0.x 覆盖安装或在应用内更新即可，数据保留。
- 悬浮球需要「显示在其他应用上层」权限，通知触发需要「通知使用权」，都只在你打开对应功能时才请求。

### English

**New**
- Custom quick tasks: add, edit, reorder or delete the shortcut buttons above the input under Appearance → Edit quick tasks (up to 8); each one either fills the input or sends at once.
- Ask about a photo: the paperclip offers "Take a photo" or "Choose files"; the photo lands in the attachment inbox, ready to add to the conversation.
- Math and diagrams: LaTeX in replies (`$…$`, `$$…$$`, `\(…\)`, `\[…\]`) is typeset; `mermaid` code blocks are drawn as diagrams once the reply is complete (the copy button still copies the source, and a diagram that can't be drawn stays as source).
- Memory: a new Memory page shows what the AI remembers about you and lets you add, edit or delete it. The AI saves useful facts on its own, within limits: at most 30 memories of up to 200 characters, at most 3 automatic saves per task, no near-duplicates, and never passwords, keys, verification codes or ID numbers. Conversations include only the newest memories (about 2,000 characters) to keep token use down. Automatic memory, or memory altogether, can be turned off.
- Edit and regenerate: copy your messages or edit and resend them, and regenerate the latest reply; this replaces the rest of the conversation (file changes are not undone).
- Model profiles: save your usual providers and models and switch in one tap. Switching between cloud models, or changing the model or reasoning effort, no longer restarts the engine; switching to or from the on-device model still does. API keys stay in the system keystore per provider address; profiles never contain them.
- Backup and restore: export every conversation, memories, schedules and workflows, the built-in workspace's files and your model and interface settings as one zip, and restore it on a new phone or after reinstalling. API keys, downloaded on-device models and the toolchain are left out; the data from before a restore is kept.
- Background services: the AI can start programs that keep running after the task (a local web server, a bot, a watcher). The new Background services page shows their output and lets you open them in the browser, stop, restart or delete them, and start them with the engine; optionally they keep running with the screen off.
- Long commands: installs and builds can now run for up to 30 minutes, with their output streaming into the tool card. Previously every tool stopped after 2 minutes.
- Global entry: an "Ask Agent" quick settings tile; a floating bubble you can drag (tap for a new conversation, long-press to ask about the screen, ask by voice or hide it); and New chat, Ask by voice and Ask about a photo when you long-press the app icon.
- Built-in browser: the AI can use the phone's WebView to open web pages, read pages that need JavaScript, click, fill in forms, press Enter and take screenshots. Opening pages, clicking and filling need your approval; reading or capturing the current page doesn't. Its sign-ins are kept apart from the app's interface, and Device & tools can test it or clear its data.
- Notification rules: when a notification arrives from an app you chose (optionally only with certain keywords), the AI handles it the way you describe, for example "note the pickup code when a parcel text arrives". By default each run asks you first through a notification; only the chosen apps' notifications are read and their content goes only to the triggered task; each rule runs at most once every 30 seconds and 30 times a day. You grant notification access in system settings.

**Fixes**
- Settings fields and drop-downs (such as the model name and workspace path) lost their styling in 1.0.1; fixed.
- After an update, an engine that the background recovery job had already started kept running the old code, so the interface stayed on the previous version. Opening the app after an update now restarts the engine.

**Upgrading**
- Install over 1.0.x or update from inside the app; data is kept.
- The floating bubble needs permission to display over other apps and notification rules need notification access; both are requested only when you turn the feature on.

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

**兼容性**
- 修复 Android 15+ 使用 16 KB 内存页的新机型上引擎无法启动（卡在「等待本地服务凭据」）：内置 SQLite 库升级到 3.50.4，所有原生库均为 16 KB 对齐，构建时自动检查。
- 系统 WebView 被停用、缺失或正在更新时不再闪退，改为显示说明页，可一键去更新或启用 WebView、导出日志。
- WebView 内核低于 Chrome 80 时，启动时提示更新，不再白屏；最低要求从 Chrome 86 降到 80。
- 旧版 WebView 不支持液态玻璃所需样式时自动使用标准风格，避免面板透明到看不清；设置页输入框在旧内核上也有正常样式。
- 退出小米 / 澎湃、ColorOS、MagicOS 等的「强制深色模式」，界面不会被二次反色。
- 折叠屏展开 / 折叠、分屏调整大小、接入外接键盘时不再重新加载界面。
- 打开没有对应应用的文件类型（如 .md、.py）时，改为让你选择文本查看器或任意应用。
- 定时任务、引擎恢复的通知和通知类别名称改为中英文。

**新增**
- 加载页右上角新增「导出日志」与「检查更新」（与「模型设置」并排），进不去应用也能用。导出日志可分享文件、保存到手机，或一键打开 GitHub 新建 Issue 页面并预填脱敏后的启动日志摘要（需登录 GitHub，由你确认后提交）。
- 应用内更新（OTA）：每天自动检查 GitHub 是否有新版本（可在「设备与工具 → 版本与更新」关闭），也可手动检查；下载后校验 SHA-256、包名与签名，再交给系统安装器由你确认安装。首次安装更新时需按提示允许「安装未知应用」。

**升级说明**
- 从 1.0.0 直接覆盖安装即可，数据保留。从 1.0.1 起，之后的版本可在应用内更新。
- 1.0.1 的安装包在 2026-10-06 当天更新过一次（加入上面的兼容性修复）。如果当天已经装过较早的 1.0.1，应用内更新不会再提示同版本号，请从发布页重新下载覆盖安装，数据保留。

### English

**Fixes**
- After a provider rejects an image (for example DeepSeek's "unsupported image" 400), the conversation no longer fails the same way on every retry or continue: the rejected image is dropped from later requests, the model is told, and the task goes on.
- `attach_image` checks the image structure first (PNG checksums, JPEG frames, GIF/WebP integrity), so truncated or fake images are never sent to the model.
- Stuck at "Waiting for the local service credentials": the app now judges a stuck engine by its start-up progress, so a slow but healthy start (first start after an update, a long task history) is no longer killed and restarted; only a start with no progress is restarted, and the loading screen shows the current step.
- Every engine start-up step, and the thread stacks of a stalled start, are written to the logs.
- Fixed shared diagnostics files that the receiving app could not open.
- Interface: a failed task no longer shows the same error twice (notice bar and error card); the glass composer, header and task status pill have more frost and tint so text scrolling behind them no longer mixes with their labels; long error notices scroll instead of covering the composer.

**Compatibility**
- Fixed the engine failing to start (stuck at "Waiting for the local service credentials") on Android 15+ devices with 16 KB memory pages: the bundled SQLite library is now 3.50.4, every native library is 16 KB aligned, and the build checks this.
- A disabled, missing or updating system WebView no longer crashes the app; a help screen offers to update or enable WebView and to export logs.
- A WebView older than Chromium 80 gets an update prompt at start-up instead of a blank page; the minimum dropped from Chromium 86 to 80.
- Where an older WebView lacks the styles liquid glass needs, the standard style is used instead of unreadable see-through panels; settings fields keep their styling on older engines.
- Opted out of vendor "force dark" modes (MIUI/HyperOS, ColorOS, MagicOS …) so the interface is not inverted a second time.
- Folding or unfolding, resizing in split screen and connecting a keyboard no longer reload the interface.
- Files whose type no installed app claims (such as .md or .py) now open through a chooser of text viewers or any app.
- Scheduled-task and engine-recovery notifications and their channel names are now in Chinese and English.

**New**
- "Export logs" and "Updates" on the loading screen next to "Model settings", usable even when the app cannot get past start-up. Export can share the file, save it to the phone, or open a new GitHub issue prefilled with a masked start-up log summary (you sign in to GitHub and submit it yourself).
- In-app updates (OTA): a daily check for a new GitHub release (can be turned off under Device & tools → Version and updates) and a manual check; the download is verified (SHA-256, package name and signature) before Android's installer asks you to confirm. The first update asks you to allow installing unknown apps.

**Upgrading**
- Install over 1.0.0; data is kept. From 1.0.1 on, later versions can be installed from inside the app.
- The 1.0.1 package was replaced once on 2026-10-06 to add the compatibility fixes above. If you installed the earlier 1.0.1 that day, the in-app updater will not offer the same version number again; download it from the release page and install over it (data is kept).

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
