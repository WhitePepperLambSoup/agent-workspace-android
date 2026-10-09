# Changelog

## 1.1.1 — 2026-10-09

本机模型改进版。On-device model release.

### 中文

**本机模型：更快**
- 新对话不再从头计算系统提示（指令与工具说明，约 1,600 Token）：算过一次后保存在手机上，之后的新对话直接复用，引擎释放内存后也能恢复。在骁龙 888 上用 Qwen3.5 2B，新对话的首 Token 从约 60 秒降到 1–2 秒，一句话问答从约 80 秒降到约 20 秒。每个模型最多保留 3 份，删除模型时一起删除。
- 同一任务的后续步骤只计算新增的内容，不再每一步把整段对话重算一遍。
- 支持 ARMv8.2 点积与 FP16 指令的芯片（如骁龙 8 系、天玑 9000 系）自动使用加速版推理库：输入处理快约 58%，生成快约 29%。不支持的芯片自动使用通用版。
- 「本地模型」页新增 CPU 指令、输入处理速度、复用输入和推理线程。

**本机模型：更稳、更凉**
- 修复明明内存够用却提示「内存不足」：可用内存现在包含系统可立即回收的部分；模型加载后推荐的上下文不再虚高。页面分别显示「可用于模型的内存」和「系统空闲内存」。
- 发热控制：生成过程中每 5 秒检查一次温度，按系统的热余量把推理线程从 4 降到 2、再降到 1。长任务时机身稳定在约 47–48°C，不再触发系统的高温保护。
- 使用本机模型执行任务时保持亮屏，避免部分机型在息屏后强制结束占用内存较大的引擎进程。
- 小模型调用工具更可靠：调用不存在的工具或格式写错时，会说明原因让模型重试，不再让整个任务失败；按你的请求预先提供需要的工具（运行命令、修改文件、上网、操作手机等），不必等小模型自己挑选。
- 小模型写文件时编造或抄错的文件校验值，会按对话中实际读到的值修正；文件在此期间被改动过仍会拒绝写入。新建文件时编造的校验值按新建处理。
- 对话历史不再把工具参数里 HTML 的 `<` 写成 `<`，避免模型照抄转义写法导致修改对不上原文。
- 报错更明确：`python3` 等命令未安装时，说明需要可选的开发工具链并提示不要重试；修改文件时原文找不到，会指出最接近的那段原文及行号；文件校验不符时，说明是该新建还是需要重新读取。

**其他修复**
- 运行 AI 生成的网页时，用 localStorage 保存数据的页面（如待办清单）不再报错，添加和勾选都能用；数据只在本次预览中有效。
- 消息中的 HTML 标签（如 `</style>`、`<b>`）按原文显示，不再消失；表格中的 `<br>` 显示为换行。

**升级说明**
- 覆盖安装或在应用内更新即可，数据保留。
- 换用本机模型后的第一个对话仍需约 1 分钟计算系统提示，之后的新对话就很快了。

### English

**On-device models: faster**
- New conversations no longer evaluate the system prompt (instructions and tool schemas, about 1,600 tokens) from scratch: it is evaluated once, saved on the phone, and reused by later conversations, even after the engine frees its memory. With Qwen3.5 2B on a Snapdragon 888, the first token of a new conversation went from about 60 seconds to 1–2 seconds, and a one-sentence answer from about 80 seconds to about 20. At most three are kept per model, and removing a model removes them.
- Later steps of a task evaluate only what is new instead of the whole conversation again.
- Chips with ARMv8.2 dot-product and FP16 instructions (such as Snapdragon 8 series and Dimensity 9000 series) use an accelerated inference library: prompt processing about 58% faster and generation about 29% faster. Other chips keep the baseline library.
- The Local models page shows the CPU instructions in use, prompt processing speed, reused input and inference threads.

**On-device models: steadier and cooler**
- Fixed "not enough memory" on phones with plenty to spare: usable memory now includes what the system can reclaim at once, and the recommended context no longer inflates once a model is loaded. The page lists "Memory for the model" and "System free memory" separately.
- Heat control: during generation the temperature is checked every 5 seconds and inference threads drop from 4 to 2 to 1 by the system's thermal headroom. Long tasks hold the phone at about 47–48 °C instead of tripping the system's overheat protection.
- The screen stays on while a task runs on the on-device model, so phones that kill a large engine process once the screen turns off no longer end the task.
- More reliable tool use by small models: an invented tool or a malformed call is explained and retried instead of failing the task, and each request starts with the tools it asks for (commands, file edits, the web, phone control) rather than waiting for a small model to select them.
- A made-up or mis-copied file checksum from a small model is corrected to the value the conversation actually read; if the file changed in the meantime the write is still refused. A made-up checksum for a new file is treated as creating it.
- Conversation history no longer writes `<` in HTML tool arguments as `<`, which models copied into edits that then failed to match the file.
- Clearer errors: a missing command such as `python3` says that it comes with the optional developer toolchain and not to retry; an edit whose original text is not found points to the closest text and its line numbers; a checksum mismatch says whether to create the file or read it again.

**Other fixes**
- Running a generated web page that keeps data in localStorage (such as a to-do list) no longer fails; adding and checking items works, and the data lasts for that preview.
- HTML tags in messages (such as `</style>` or `<b>`) are shown as typed instead of disappearing; `<br>` in a table cell becomes a line break.

**Upgrading**
- Install over 1.1.0 or update from inside the app; data is kept.
- After switching to an on-device model, the first conversation still needs about a minute for the system prompt; new conversations after that are quick.

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
- 内置浏览器：AI 可以用手机自带的 WebView 打开网页，读取需要脚本渲染的页面，点击、填表、按回车和截图；也能直接打开工作区里自己生成的网页检查效果，无需另起网页服务。打开网页、点击和填表需要你批准，读取和截取当前页面不需要；它的登录状态与应用界面分开保存，可在「设备与工具」里测试或清除。
- 通知触发：选定应用的通知到达时（可按关键词过滤），让 AI 按你写的要求处理，例如「快递短信来了就记下取件码」。默认每次运行前先通过通知问你；只读取你选定应用的通知，内容只交给被触发的任务；每条规则至少间隔 30 秒、每天最多 30 次。需要你在系统设置里授予通知使用权。

**修复**
- 修复 1.0.1 中设置页的输入框和下拉框（如模型名、工作区路径）失去样式的问题。
- 应用更新后，若引擎在你打开应用前已被后台恢复任务启动，会继续运行更新前的代码，界面停留在旧版本。现在打开应用时检测到更新会重启引擎。
- 在对话界面按返回键有时会显示一段 `unauthorized` 文字而不是退出，现在会把应用退到后台。
- 长任务执行中，通知栏会在「执行任务」与「恢复连接」之间来回跳；对话很长时状态查询也越来越慢。现在偶发的一次查询超时不再显示为断线，任务状态改为增量读取。
- AI 用截图检查网页时，截图不再出现在任务的「生成的文件」里。
- 任务失败后点「重试」，原来的问题会留在输入框里；现在重试时一并清掉。
- 刚在新对话里聊过一轮，再从悬浮球或通知栏开新对话时，会沿用当前对话而不是新建。
- 自动记忆更克制：只记你明确说过的关于自己的事，不再把单次任务的内容（如“关注某研究方向”）或任务中启动的服务、端口当成记忆。
- 你或 AI 主动停止的后台服务，即使勾选了「随引擎启动」，也不会在引擎重启或应用更新后自己跑起来。
- 下载文件、网页读取失败时，错误信息会说明原因（如超时、连接被重置），方便 AI 判断是否重试。
- 应用内输入框弹窗（如给模型配置命名、输入包名）的文字在浅色模式下看不清；通知触发规则添加后，应用选择框会清空；截图提问的提示不再显示为错误样式；后台服务的状态文字不再被拆成两行。

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
- Built-in browser: the AI can use the phone's WebView to open web pages, read pages that need JavaScript, click, fill in forms, press Enter and take screenshots. It can also open a page it built in the workspace to check it, without starting a web server. Opening pages, clicking and filling need your approval; reading or capturing the current page doesn't. Its sign-ins are kept apart from the app's interface, and Device & tools can test it or clear its data.
- Notification rules: when a notification arrives from an app you chose (optionally only with certain keywords), the AI handles it the way you describe, for example "note the pickup code when a parcel text arrives". By default each run asks you first through a notification; only the chosen apps' notifications are read and their content goes only to the triggered task; each rule runs at most once every 30 seconds and 30 times a day. You grant notification access in system settings.

**Fixes**
- Settings fields and drop-downs (such as the model name and workspace path) lost their styling in 1.0.1; fixed.
- After an update, an engine that the background recovery job had already started kept running the old code, so the interface stayed on the previous version. Opening the app after an update now restarts the engine.
- Pressing Back in the conversation sometimes showed an `unauthorized` message instead of leaving; it now sends the app to the background.
- During long tasks the notification flipped between "running" and "reconnecting", and status checks slowed down as conversations grew. A single slow status check no longer counts as a disconnect, and task status is now read incrementally.
- Screenshots the AI takes to check a web page no longer appear among the task's generated files.
- Retrying a failed task left the original prompt in the input; retrying now clears it.
- Right after a first exchange in a new conversation, the floating bubble or the quick settings tile reused that conversation instead of opening a new one.
- Automatic memory is more restrained: it keeps only what you say about yourself, not the content of a single task (such as "interested in a research topic") or the services and ports a task started.
- A background service that you or the AI stopped no longer starts again after an engine restart or app update, even when "Start with the engine" is checked.
- Failed downloads and page fetches now say why (for example a timeout or a reset connection), so the AI can decide whether to retry.
- Text in the app's input dialogs (such as naming a model profile or entering a package name) was hard to read in light mode; the app picker clears after a notification rule is added; the screenshot prompt no longer looks like an error; a background service's state no longer wraps onto two lines.

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
