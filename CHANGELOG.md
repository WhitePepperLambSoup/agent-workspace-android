# Changelog

## 1.3.0 — 2026-10-11

功能版：圈选提问、离线语音识别、桌面小组件，长任务更顺畅。Feature release: circle to ask, offline speech recognition, home screen widgets, and smoother long tasks.

### 中文

**圈选提问（新）**
- 长按悬浮球选「圈选提问」：屏幕定格成截图，圈出想问的部分（或直接用整屏），就会开一个新对话把它发给 AI。
- 没开无障碍服务时，每次通过系统的截屏授权，只截一帧就停止；开启无障碍服务后直接截图。屏幕上有密码框时不截图。

**离线语音识别（新）**
- 在「本地模型」下载 SenseVoice Small 语音模型（约 239 MB，可选 Hugging Face 或 ModelScope）后，输入框的麦克风会在手机上识别中文、英文、日语、韩语和粤语。录音不上传也不保存，说完停顿一下会自动结束。
- AI 可以把工作区里的录音和视频转成带时间戳的文字，长录音会分段接续。
- 识别引擎是 sherpa-onnx（内含 ONNX Runtime），只随 64 位 ARM 版本打包，安装包约增大 8.6 MB；x86_64 设备继续使用系统语音识别。

**桌面小组件（新）**
- 「快捷提问」（4×1）：像搜索框一样开新对话，也能直接语音或拍照提问。
- 「任务动态」（4×2）：显示等待批准、正在执行或最近的任务，点一下直达那个对话。
- 「常用任务」（4×2）：输入框上方的常用任务，点一下开新对话并填好指令。
- 在菜单 →「全局入口」一键添加，或长按桌面空白处从「小组件」里添加。组件跟随系统浅色 / 深色；应用选液态玻璃风格时，组件也换成玻璃样式。

**长任务**
- 审批新增「本任务内都允许」：这个任务后续的网络请求和工具调用不再逐个询问，任务结束即失效；删除文件、写入长期记忆、操作其他应用仍然每次询问。此前在「仅工作区」模式下，一个多步骤任务可能要批准几十次。
- AI 的回复、进度说明和总结都使用你提问的语言（此前中文提问有时会收到英文回复）。
- 网页读取：支持 GBK / GB2312 等中文编码的网站；网站的 IPv6 地址连不通时自动改用其他地址；允许同一网站内的跳转（如 example.com 跳到 www.example.com）。
- 网页搜索：改为读取必应网页结果，并按查询的语言发出请求，修复部分网络下搜索结果与问题毫不相关；DuckDuckGo 连不上时 10 分钟内优先用必应，不再每次先等它失败。
- PDF：生成的中文 PDF 从约 8 MB 降到几百 KB（不再嵌入整套系统字体）；在 PDF 里复制、搜索文字也都正确。
- 已在手机上验证：执行中追加要求、中途停止、应用被强行关闭后恢复任务。

**更快、更省电**
- 新对话发出第一条消息前的准备时间从几秒降到约 0.1 秒；冷启动快约 1 秒。
- 界面空闲时不再持续重绘；等待审批时动画停下；进行中的动画降低帧率，更省电。

**界面**
- 空白的新会话不再越积越多：在空白会话上点「新建」会直接使用它，离开从未使用的空白会话会自动删除（写了草稿的会保留）。
- 审批卡片用文字说明数据发往哪里、包含哪些内容；工具结果直接显示正文（例如转写出的文字），不再是一大段原始数据。
- 启动等待页更简洁，「导出日志」「检查更新」「模型设置」只在启动变慢或失败时出现。

**升级说明**
- 覆盖安装或在应用内更新即可，数据保留。离线语音识别需要先在「本地模型」下载语音模型；小组件在菜单 →「全局入口」添加。

### English

**Circle to ask (new)**
- Long-press the floating bubble and choose "Circle to ask": the screen freezes as a screenshot, and the part you circle (or the whole screen) goes to the AI in a new conversation.
- Without the accessibility service, each capture goes through Android's screen-capture consent and takes a single frame; with the service on, the screenshot is taken directly. Nothing is captured while a password field is on screen.

**Offline speech recognition (new)**
- Download the SenseVoice Small speech model (about 239 MB, from Hugging Face or ModelScope) under Local models, and the microphone button recognises Chinese, English, Japanese, Korean and Cantonese on the phone. Recordings are neither uploaded nor kept; a short pause ends the input.
- The AI can transcribe recordings and videos in the workspace into timestamped text, continuing long recordings in parts.
- The recogniser is sherpa-onnx (with ONNX Runtime), packaged for 64-bit ARM only, adding about 8.6 MB to the APK; x86_64 devices keep using the system recogniser.

**Home screen widgets (new)**
- "Quick ask" (4×1): a search-bar-like entry to a new conversation, with voice and photo buttons.
- "Task status" (4×2): the task waiting for approval, running or finished last; tap it to open that conversation.
- "Quick tasks" (4×2): the quick tasks above the input; one tap starts a new conversation with the prompt filled in.
- Add them from Menu → Global entry, or from Widgets after long-pressing the home screen. They follow the system's light or dark mode, and take a glass look when the app uses the liquid-glass style.

**Long tasks**
- New approval scope "Everything in this task": later network requests and tool calls of the same task no longer ask one by one, until the task ends. Deleting files, changing long-term memory and operating other apps still ask every time. In workspace mode a multi-step task could previously ask for approval dozens of times.
- Replies, progress notes and summaries use the language of your question (a Chinese question sometimes got an English answer).
- Reading web pages: sites in GBK / GB2312 and other Chinese encodings now load; when a site's IPv6 address is unreachable, its other addresses are tried; redirects within one site (example.com to www.example.com) are followed.
- Web search reads Bing's result pages in the language of the query, fixing results unrelated to the question on some networks; when DuckDuckGo is unreachable, Bing goes first for 10 minutes instead of waiting on DuckDuckGo every time.
- PDF: a Chinese PDF is now a few hundred KB instead of about 8 MB (the whole system font is no longer embedded), and copying or searching its text works correctly.
- Verified on a phone: adding instructions to a running task, stopping it, and resuming after the app was force-closed.

**Faster, lighter on the battery**
- Preparing a new conversation's first message takes about 0.1 s instead of several seconds; a cold start is about 1 s quicker.
- The interface no longer redraws continuously while idle; animations stop while waiting for an approval and run at a lower frame rate otherwise.

**Interface**
- Empty "New conversation" entries no longer pile up: New on an empty conversation reuses it, and an empty conversation you leave unused is removed (one with a draft is kept).
- Approval cards say in words where data goes and what it contains; tool results show their main text, such as a transcript, instead of raw data.
- The loading screen is cleaner: Export logs, Updates and Model settings appear only when start-up is slow or fails.

**Upgrading**
- Install over the existing app or update in the app; your data is kept. Offline speech recognition needs the speech model from Local models; add widgets from Menu → Global entry.

## 1.2.1 — 2026-10-10

修复版：悬浮球截屏提问的截图会加到上一个会话。Hotfix: a floating-bubble screenshot could be attached to the previous conversation.

### 中文

- 修复用悬浮球「截屏提问」时，如果当前会话里已有内容，截图会被加到这个旧会话的输入框，而不是新开的会话：新会话里看不到截图，AI 只能自己去工作区里找。原因是截图接收完成得比新会话创建还早。现在会等新会话建好后再把截图加进去；新会话没能创建时，截图留在附件收件箱里，可以手动添加。

**升级说明**
- 覆盖安装或在应用内更新即可，数据保留。之前误加到旧会话输入框里的截图，可以点截图旁的 × 移除。

### English

- Fixed "Ask about the screen" from the floating bubble attaching the screenshot to the conversation that was open, when that conversation already had messages, instead of the new one it opened: the new conversation showed no screenshot and the AI had to look for it in the workspace. The screenshot arrived before the new conversation was created. It is now attached once the new conversation is ready; if the conversation could not be created, the screenshot waits in the attachment inbox to be added by hand.

**Upgrading**
- Install over the existing app or update in the app; your data is kept. A screenshot that was added to an older conversation's draft can be removed with the × next to it.

## 1.2.0 — 2026-10-10

功能版：知识库、闹钟与日历，本机模型更可靠。Feature release: a knowledge base, alarms and calendar, and more reliable on-device models.

### 中文

**知识库（新）**
- 菜单 →「知识库」：把说明书、合同、笔记、电子书加进来，提问时 AI 会从中找出相关段落回答，并注明出自哪份文档、第几页。支持 PDF（需要有文字层，扫描件暂不支持）、Word（.docx）、Excel（.xlsx）、EPUB、网页、Markdown 和文本文件。
- 三种添加方式：在知识库页选择文件；在工作区文件预览里点「加入知识库」；或在对话里说「把 xx.pdf 加入知识库」。
- 文档只保存在这台手机上，按关键词检索（SQLite 全文索引，中文按双字切分），不用下载模型，也不消耗额度。单个文件最大 100 MiB，最多 300 份；可以重命名、删除，也可以在页面里直接试搜。
- 换个说法也能找到：内置 161 组中英文常用说法（如「房租」和「租金」、「坏了」和「维修」），也可以在页面里加上自己的同义词。主动搜索时，文档里没有的中文词还会按单字去找，比如搜「房租」也能找到写着「租金」的段落。
- 「提问时自动附上相关段落」：开启后每次提问会先在知识库里找，找到相关段落才随问题一起发给模型；关闭后只在 AI 主动搜索时使用。段落会标明是参考资料交给模型，而不是给 AI 的指令。

**闹钟、计时与日历（新）**
- 让 AI 在系统时钟里设闹钟（指定时间或几分钟后，可每周重复）和倒计时。应用在后台时安卓不允许直接打开时钟，这时会发一条通知，点一下即可完成设置。
- 在「设备与工具 → 日历」允许访问后，AI 可以查看和添加日程。在「工作区」执行模式下，每次添加日程前都会请你批准。
- AI 现在知道今天的日期、星期和时区，「明天下午三点」这类说法能正确换算。

**本机模型**
- 模型下载来源可选 ModelScope 魔搭（国内 CDN）或 Hugging Face。默认自动选择：中文界面先连 ModelScope，英文界面先连 Hugging Face，连不上再换另一个；暂停后换个来源会接着下载，下载完都按固定的 SHA-256 校验。
- 工具调用加了语法约束（GBNF）：模型开始写工具调用时，只能写出格式正确的内容，不再因为格式错误被退回重试。在 12 个日常任务的测试中，Qwen3.5 0.8B 完成的任务从 6 个增加到 7 个，模型调用从 41 次减少到 29 次；2B 保持 11 个。「本地模型」页会显示本轮是否启用了约束、纠正了几次。
- 提示更短、首字更快：工具说明更精简，并按你的请求只附上需要的工具（浏览器这类说明较长的工具只在提到时才附上）；记忆部分也更紧凑。
- 新增「复制文件」工具：小模型复制文件时一次完成，不再把内容逐字重写一遍，也不会把读取结果的格式混进副本。新建文件夹时会自动创建上级文件夹，文件夹已存在也视为完成。
- 自动上下文最大取 32K Token：更大的上下文会多占内存、加载更慢（Qwen3.5 0.8B 用 128K 时常驻内存约 2.3 GiB，32K 时约 1 GiB）。需要的话仍可以手动选择更大的上下文。

**界面**
- 菜单顶部新增搜索框：按名称或关键词（中英文都可以）找到功能，以及各页面里的具体设置。
- 新增「关于与更新」页：检查更新、每天自动检查和导出诊断日志都集中在这里（原来在「设备与工具」）。
- 重新打开会话时，只调用了工具、没有文字的步骤不再显示成空白的回复卡片。

**修复**
- 包含 1.1.2 的修复：Android 15 及以上的手机可能打不开应用。

**升级说明**
- 覆盖安装或在应用内更新即可，数据保留。
- 新增「设置闹钟」和「日历」权限声明。日历权限只在你点「设备与工具 → 日历」时才会请求；闹钟和计时不需要你另外授权。

### English

**Knowledge base (new)**
- Menu → Knowledge base: add manuals, contracts, notes and e-books, and the AI answers from the relevant passages, citing the document and, when known, the page. Supports PDF (with a text layer; scans are not supported yet), Word (.docx), Excel (.xlsx), EPUB, web pages, Markdown and text files.
- Add documents from the Knowledge base page, with "Add to the knowledge base" in the workspace file preview, or by saying "add xx.pdf to the knowledge base" in a conversation.
- Documents stay on this phone and are searched by keyword (an SQLite full-text index; Chinese is split into two-character units), so no model download and no API usage. Up to 100 MiB per file and 300 documents; documents can be renamed and deleted, and the page has a test search.
- Other wordings still match: 161 built-in groups of common Chinese and English wordings (for example "repair", "fix" and "maintenance"), plus your own groups on the page. Explicit searches also look up a Chinese word that no document contains by its single characters, so 房租 (rent) still finds a passage about 租金 (rental fee).
- "Attach relevant passages to each question": when on, every question is first looked up in the knowledge base, and passages are sent with it only when they match; when off, the knowledge base is used only when the AI searches it. Passages reach the model marked as reference material, not as instructions.

**Alarms, timers and calendar (new)**
- The AI can set alarms (at a time or in some minutes, optionally repeating on weekdays) and timers in the system Clock app. Android does not let an app in the background open the Clock app, so in that case a notification appears; tap it to finish.
- After you allow calendar access under Device & tools → Calendar, the AI can list and add events. In the Workspace execution mode, every new event needs your approval.
- The AI now knows today's date, weekday and time zone, so "tomorrow at 3 pm" resolves correctly.

**On-device models**
- Models can be downloaded from ModelScope (a mainland China CDN) or Hugging Face. Automatic tries ModelScope first in the Chinese interface and Hugging Face first in the English one, and falls back to the other if the first can't be reached. After a pause, another source continues where the download stopped. Every download is checked against its pinned SHA-256.
- Tool calls are constrained by a grammar (GBNF): once the model starts a tool call, it can only write a well-formed one, so calls are no longer rejected for bad formatting. On 12 everyday tasks, Qwen3.5 0.8B finished 7 instead of 6 with 29 model calls instead of 41; 2B stayed at 11. The Local models page shows whether the grammar was active in the last run and how often it corrected the model.
- Shorter prompts and a faster first token: tool descriptions are shorter, only the tools your request needs are included (long ones such as the browser only when you mention them), and the memory section is more compact.
- A new copy_file tool lets small models copy a file in one call instead of rewriting it token by token, which could also paste the read result's wrapper into the copy. Creating a folder now creates missing parent folders and treats an existing folder as done.
- The automatic context size is capped at 32K tokens: a larger context uses more memory and loads more slowly (Qwen3.5 0.8B kept about 2.3 GiB resident at 128K against about 1 GiB at 32K). You can still choose a larger context by hand.

**Interface**
- A search box at the top of the menu finds features and the individual settings inside each page, by name or keyword, in Chinese or English.
- A new About and updates page gathers update checks, the daily automatic check and diagnostic log export (previously under Device & tools).
- When a conversation is reopened, steps that only called tools no longer show as empty reply cards.

**Fixed**
- Includes the 1.1.2 fix for the app failing to open on Android 15 and later.

**Upgrading**
- Install over the existing app or update in the app; your data is kept.
- The app now declares the "set alarm" and calendar permissions. Calendar access is requested only when you tap Device & tools → Calendar; alarms and timers need no extra permission.

## 1.1.2 — 2026-10-10

修复版：Android 15 及以上的手机可能打不开应用。Hotfix: the app could fail to open on Android 15 and later.

### 中文

- 修复在 Android 15 及以上的手机上（例如三星 Galaxy S23，Android 16）应用打不开、一直停在「正在连接」：后台引擎原本使用「数据同步」类前台服务，Android 15 起这类服务每 24 小时最多运行 6 小时。额度用完后系统会停止引擎，再打开应用时引擎一启动就崩溃，并反复重启。引擎现在改用 Android 为长期运行的本地服务提供的类型，不受这个时长限制；即使系统仍拒绝前台通知，引擎也会在应用打开期间照常运行，不再崩溃。
- 同一原因也会让引擎在一天累计运行约 6 小时后被系统停止，提示「Android 已限制后台执行」。这一问题一并修复。

**升级说明**
- 覆盖安装即可，数据保留。已经打不开的手机，从本页下载 APK 覆盖安装后即可正常打开。

### English

- Fixed the app failing to open on Android 15 and later (for example a Samsung Galaxy S23 on Android 16), stuck at "Connecting": the engine ran as a "data sync" foreground service, which Android 15 limits to 6 hours in any 24. Once that budget was used, Android stopped the engine, and when the app was opened again the engine crashed on start and was restarted over and over. The engine now uses Android's foreground service type for long-running local services, which has no such limit, and if Android still refuses the foreground notification the engine keeps running while the app is open instead of crashing.
- For the same reason the engine was stopped after about 6 hours of use in a day, with "Android restricted background work". This is fixed too.

**Upgrading**
- Install over the existing app; your data is kept. If the app no longer opens, download the APK from this release and install it over the current one.

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
