# Android Agent GitHub 对比调查

核查日期：2026-09-30。结论针对当前工作区源码与已交付 APK 的启动路径。

## 结论

Agent Workspace 的长项是共享 Python Agent 核心、持久任务、执行审批、工作区文件处理、研究证据与费用可观察性。它已经有可用的手机工作台基础。

以 Android 系统 Agent 衡量，当前 APK 的屏幕感知、跨 App 操作和动作后验证明显不完整。Operit、Zafiro、ClosePaw 等项目已经有这些能力的具体源码。以手机编程工作台衡量，AndroidHarness、AndCode、RikkaHub 也是直接竞品，其中部分原生功能和工具链比我们丰富。

当前最值得投入的是接通 Android 执行能力、建立屏幕反馈闭环和实际任务评测。扩大模型名称列表、增加 Markdown 或 YOLO，已经难以形成明显差异。

## 范围与方法

- 进行了 10 轮 GitHub 关键词搜索，取得 140 个去重候选。候选包含无关仓库；这个数字不是 140 个有效竞品。
- 关键词：`android agent accessibility`、`android ai agent on device`、`android coding agent`、`android agent shizuku`、`android agent`、`phone agent`、`mobile-use`、`android openclaw`、`android local llm`、`mobile coding agent`。
- 重点核查以下 30 个代表项目的 README、仓库元数据和维护记录，并抽查关键源码、Manifest、工具注册、执行循环或安装流程。
- 默认分支源码和已发布 APK 分开判断。提交日期使用默认分支最新 commit，不用 `updated_at` 或其他分支的 `pushed_at` 代替。
- 没有安装运行竞品，也没有进行相同模型、设备、任务预算下的成功率比较。README 功能声明不等于实机可靠性证明。
- 作者报告的 AndroidWorld、MobileWorld 等成绩不组成本文的排名；模型、预算、重试、截图/UI 树、评测环境不同，会影响比较。
- 本次新增调查文档。此前 Android 验证记录可见 [ANDROID_PARITY_2026-09-30.md](<ANDROID_PARITY_2026-09-30.md>)，其测试覆盖不能证明全部平台工具或系统自动化任务都可用。

## 手机端系统 Agent

这些项目直接提供 Android 手机上的 Agent 或系统工具。手机上运行执行循环，仍可能把截图、文本发给远程模型。

| 项目 | 已核实的能力与部署方式 | 主要限制 | 默认分支提交 / 许可 |
| --- | --- | --- | --- |
| [Operit](https://github.com/AAswordman/Operit) | 原生综合平台；文件/代码工作区、PRoot 终端、MCP/Skills、浏览器和工作流；无障碍 XML、元素点击、输入、手势；本地 PhoneAgent 循环。模型工厂含 MNN、llama.cpp Provider。 | Android 8+、ARM64；终端和模型资源较重。虚拟显示依赖 Shizuku 和机型；不能据此推断所有手机都能后台跨 App 操作。 | 2026-09-18；LGPL-3.0；v1.12.2 同日发布。 |
| [OmniBot](https://github.com/omnimind-ai/OmniBot) | Kotlin 宿主 + Flutter UI；无障碍系统工具和工作区；OmniFlow Python harness 接收截图/XML，编排在手机。 | minSdk 29；GUI 插件与模型路由需要另行设置。当前 GUI `waiting_input` 路径有未接通的交互限制；Remote Codex 模式另需电脑。 | 2026-09-29；自定义分段双许可，含非商业等限制；v0.6.3.3 为预发布。 |
| [Zafiro](https://github.com/niki914/zafiro) | Compose + Chaquopy，路线与我们接近；Shell、MCP/Skills、工作区、SSH；UI 树带快照版本与节点编号，写操作后返回更新的树。 | Android 11+；截图目前走 Root/Shizuku，无障碍截图兜底未实现；无树界面会受限。替换部分系统语音助手另需 Root/LSPosed。 | 2026-09-29；MIT；1.4.2 在 09-27 发布。 |
| [ClosePaw](https://github.com/imoonkey/closepaw) | 手机 ReAct 循环、多窗口 UI 树与截图、浮动控制、暂停/接管、子 Agent、应用分级审批。 | Android 12+；虚拟显示/Chrome CDP 需 Shizuku，完整 Shell 需 Termux；本地模型路径尚未在 UI 开放。 | 2026-06-05；Apache-2.0；v0.1.0 在 05-28 发布。 |
| [PhoneAgent 原作者](https://github.com/MR-MaoJiu/PhoneAgent) | 原生视觉、无障碍、混合三模式；源码实际观察屏幕、调用模型、执行点击/输入/滑动，并支持接管。 | Android 7+；视觉模式需 MediaProjection 授权；主要是 GUI 执行循环，综合工作区与扩展生态较少；长时间未更新。 | 2025-12-12；LICENSE 正文 MIT；v1.1.0 同日发布。 |
| [FlutterClaw](https://github.com/flutterclaw/flutterclaw) | 手机上的 gateway/Agent、MCP、子 Agent、多消息渠道、PRoot Shell；Android 无障碍动作与元素查找；设备、联系人、日历、语音、通知和调度工具。 | 自称 early alpha；多个能力需要权限、额外服务或配置；“24/7”声明没有消除 Android 后台限制。 | 2026-06-13；MIT；v1.0.19 同日发布。 |

关键代码证据：

- Operit：[AccessibilityUITools](https://github.com/AAswordman/Operit/blob/main/app/src/main/java/com/ai/assistance/operit/core/tools/defaultTool/accessbility/AccessibilityUITools.kt#L78)、[PhoneAgent](https://github.com/AAswordman/Operit/blob/main/app/src/main/java/com/ai/assistance/operit/core/tools/agent/PhoneAgent.kt#L119)、[MNN/llama.cpp Provider 工厂](https://github.com/AAswordman/Operit/blob/main/app/src/main/java/com/ai/assistance/operit/api/chat/llmprovider/AIServiceFactory.kt#L469)。
- OmniBot：[无障碍服务](https://github.com/omnimind-ai/OmniBot/blob/main/accessibility/src/main/java/cn/com/omnimind/accessibility/service/AssistsService.kt#L8)、[GUI 插件架构](https://github.com/omnimind-ai/OmniBot/blob/main/omniflow-android/README.md)、[VLM 工具处理](https://github.com/omnimind-ai/OmniBot/blob/main/app/src/main/java/cn/com/omnimind/bot/agent/tool/handlers/VlmToolHandler.kt#L72)。
- Zafiro：[版本化 UI 树与操作](https://github.com/niki914/zafiro/blob/main/agent-runtime/src/main/java/com/niki914/zafiro/chat/agentic/buildin/impl/ScreenOperationAccessibilityBuiltin.kt#L23)、[截图工具](https://github.com/niki914/zafiro/blob/main/agent-runtime/src/main/java/com/niki914/zafiro/chat/agentic/buildin/impl/ScreenshotBuiltin.kt#L22)。
- ClosePaw：[观察通道](https://github.com/imoonkey/closepaw/blob/main/app/src/main/kotlin/ai/closepaw/platform/AccessibilityPlatform.kt#L64)、[策略引擎](https://github.com/imoonkey/closepaw/blob/main/app/src/main/kotlin/ai/closepaw/tool/PolicyEngine.kt#L70)。
- PhoneAgent：[实际执行循环](https://github.com/MR-MaoJiu/PhoneAgent/blob/main/app/src/main/java/com/mobileagent/phoneagent/agent/PhoneAgent.kt#L275)。
- FlutterClaw：[原生无障碍服务](https://github.com/flutterclaw/flutterclaw/blob/master/android/app/src/main/kotlin/ai/flutterclaw/flutterclaw/FlutterClawAccessibilityService.kt)、[Agent UI 工具](https://github.com/flutterclaw/flutterclaw/blob/master/lib/tools/ui_automation_tools.dart)。

## 手机编程与工作区

| 项目 | 值得比较的能力 | 对我们的意义与边界 | 默认分支提交 / 许可 |
| --- | --- | --- | --- |
| [AndroidHarness](https://github.com/Sanuu7/AndroidHarness) | 原生 Kotlin/Compose；文件、Git、Shell、MCP、子 Agent、Skills、预算、恢复、通知审批、Diff/editor、SSH、WorkManager 自动化、模型目录和费用。 | 与我们直接竞争。它也实现恢复和审批，因此这些是我们的长项，但不是独有能力。Manifest 没有无障碍服务，仍应归类编程工作台；09-29 新增的本地模型源码不能算 09-25 APK 已有。 | 2026-09-29；MIT；v1.2 在 09-25 发布。 |
| [AndCode](https://github.com/yuga-hashimoto/and-code) | 手机 PRoot/Alpine 工作区，安装 Git/bash/curl/rg 和多种 coding CLI；原生聊天、Diff、终端、语音、助手入口、widget、定时任务；可连接电脑 OpenCode、QR/mDNS、切换运行位置。 | Android 平台工具链、日常手机入口和远程接力比我们完整。各 CLI 支持程度不同；依赖下载的 rootfs/工具、模型服务及相应账户。PRoot 是兼容环境，不是强安全边界。 | 2026-09-23；MIT；v1.2.25 在 09-21 发布。 |
| [RikkaHub](https://github.com/rikkahub/rikkahub) | 原生多供应商 UI；MCP、多模态、Markdown/LaTeX/Mermaid、分支、记忆、模型配置 QR；现已加入 PRoot 工作区和文件/Shell 工具。 | 不能再按普通聊天客户端排除。原生模型设置、多模态与消息组织值得参考；该项目 README 当前不接受 PR。 | 2026-09-29；AGPL-3.0；2.5.5 在 09-27 发布。 |
| [OpenClaw on Android](https://github.com/aidanpark/openclaw-android) | Termux + glibc linker 路线，也有独立 Claw App，内置终端和 WebView；运行 OpenClaw、可选 coding CLI、备份/更新。 | 证明“手机独立运行 + WebView + 工具”已有竞品。通常需要较多磁盘、首次联网安装及后台配置；不能把 README 速度声明当实测。 | 2026-04-13；MIT；Claw App v0.4.0 在 03-30 发布。 |
| [BotDrop](https://github.com/zhixianio/botdrop-android) | Termux 基础上的 OpenClaw/Node 运行环境，四步安装配置、供应商设置、Telegram/Discord、后台 gateway 自动重启。 | 值得学习安装引导和服务诊断；综合系统屏幕控制不是其 README 的主能力。源码构建需准备运行时 bundle；当前构建说明为 arm64。 | 2026-09-17；GPL-3.0；v0.2.11 在 03-18 发布。 |

关键代码与产品证据：

- AndroidHarness：[功能/部署说明](https://github.com/Sanuu7/AndroidHarness/blob/main/README.md)、[应用内浏览器工具](https://github.com/Sanuu7/AndroidHarness/blob/main/app/src/main/java/com/androidharness/app/tools/BrowserTools.kt#L59)、[09-29 本地模型提交](https://github.com/Sanuu7/AndroidHarness/commit/702262b40c959520517ac685543b816c2c673824)。
- AndCode：[运行时安装与校验](https://github.com/yuga-hashimoto/and-code/blob/main/app/src/main/java/com/yugahashimoto/andcode/runtime/local/LocalRuntimeInstaller.kt)、[AlarmManager 调度](https://github.com/yuga-hashimoto/and-code/blob/main/app/src/main/java/com/yugahashimoto/andcode/feature/schedule/ScheduleManager.kt)。
- RikkaHub：[真实工作区工具注册](https://github.com/rikkahub/rikkahub/blob/master/app/src/main/java/me/rerere/rikkahub/data/ai/tools/WorkspaceTools.kt)。

## 远程控制与架构边界

| 项目 | 实际架构 | 优势及限制 | 默认分支提交 / 许可 |
| --- | --- | --- | --- |
| [DroidClaw 原版](https://github.com/unitedbyai/droidclaw) | Android APK 通过 WebSocket 回传 UI 树/截图和接收动作，Agent/LLM 循环在 server；另有 Bun + ADB CLI。 | 有手机执行器、远程设备和 Dashboard；不能说无 APK，也不能说手机独立编排。根目录未发现 LICENSE。 | 2026-02-28；许可未确认；v0.5.3 在 02-25 发布。 |
| [DroidClaw / Kira](https://github.com/levilyf/droidclaw) | Termux Node.js Agent + 本地 KiraService companion APK，读取节点、点击，调用配置的模型 API。 | 无 Root 的手机脚本路线；主仓库未包含 companion Android 源码，截图宣传与当前工具实现需区别。JS 的 MIT 不证明 APK 同许可。 | 2026-07-03；JS 仓库 MIT；companion 依赖包在 04-24 发布。 |
| [OpenGUI](https://github.com/Core-Mate/OpenGUI) | Android 无障碍执行端 + 外部 backend/harness/WorkBuddy；可使用 `adb reverse` 连接。 | Plan Supervisor、Executor Graph、模型路由与远程编排值得参考。作者明确长任务可靠性待验证；不是手机独立 Agent。 | 2026-09-24；核心与 Android client 为 BSL 1.1，部分插件 MIT。 |
| [Paseo](https://github.com/getpaseo/paseo) | 电脑上的 daemon 管理 Claude Code/Codex/OpenCode 等 CLI；Android/桌面/Web 客户端连接 daemon，支持加密 relay 或直接连接。 | 多设备协作、语音、设备配对和外部 Agent 集成比我们丰富；任务运行依赖自己的电脑/服务器，默认不是手机本地编程环境。 | 2026-09-30；LICENSE 正文 Apache-2.0；v0.10.2 在 09-29 发布。 |
| [CC Pocket](https://github.com/K9i-0/ccpocket) | 手机 Flutter UI + 主机 WebSocket Bridge + Codex/Claude。 | QR/mDNS/Tailscale、断网消息队列与流恢复、Git/worktree、媒体、平板多栏；需要运行 Bridge 的主机。最新 release 是 Windows 版本，不能当 Android 版本号。 | 2026-09-30；MIT；移动版通过商店发行。 |

架构证据：[DroidClaw ConnectionService](https://github.com/unitedbyai/droidclaw/blob/main/android/app/src/main/java/com/thisux/droidclaw/connection/ConnectionService.kt#L120)、[server loop](https://github.com/unitedbyai/droidclaw/blob/main/server/src/agent/loop.ts)、[Kira bridge](https://github.com/levilyf/droidclaw/blob/main/src/tools/kiraservice.js#L9)、[OpenGUI 无障碍服务](https://github.com/Core-Mate/OpenGUI/blob/main/client/core_accessibility/src/main/java/com/coremate/opengui/accessibility/GestureService.kt#L35)、[Paseo README](https://github.com/getpaseo/paseo/blob/main/README.md)、[CC Pocket README](https://github.com/K9i-0/ccpocket/blob/main/README.md)。

## 主机控制框架与测试工具

| 项目 | 核心能力与运行依赖 | 对我们的启发 / 限制 | 默认分支提交 / 许可 |
| --- | --- | --- | --- |
| [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) | 主机 Python + ADB/ADB Keyboard + 外部模型；截图→模型→动作，设备 ID、步骤上限、敏感动作确认与人工接管。 | 简洁手机执行循环；README 的 50+ App 属作者声明。最终完成依赖模型/handler，没有独立目标评估器。 | 2026-03-06；Apache-2.0。 |
| [Mobile-Agent / GUI-Owl](https://github.com/X-PLUG/MobileAgent) | 阿里研究模型与 runner 家族，v3.5/GUI-Owl 1.5；主机 Python、ADB、模型服务。 | 截图历史、记忆、重试和人工接管；v3 多角色设计不代表 v3.5 默认真机 runner 已有独立 verifier。 | 2026-07-07；MIT。 |
| [Mobilerun，原 DroidRun](https://github.com/droidrun/mobilerun) | 主机 Python + Android Portal APK/无障碍 + ADB；UI 树/截图、manager/executor、多供应商、结构化输出、tracing、多设备。 | 最值得参考 Android 观察/执行通道。Portal 在手机不等于完整编排也在手机；模型调用仍可能上传屏幕数据。 | 2026-09-28；MIT；v0.6.20 同日发布。 |
| [agent-device](https://github.com/callstack/agent-device) | 主机 Node/SDK/ADB + snapshot helper；CLI/MCP/Node API、refs/selectors、截图、录像、assert、replay、设备/session 锁。 | 最新快照才能使用 refs，动作 `--settle` 返回差异；适合接入我们的共享核心。规划由外部 Agent 承担。 | 2026-09-29；MIT；v0.21.15 在 09-25 发布。 |
| [mobile-use](https://github.com/minitap-ai/mobile-use) | 主机 Python/Docker + 设备调试 + LLM；UI-aware 操作、结构化抓取、多供应商。 | 作者报告较高基准成绩；不能据此换算真实中文 App 成功率。无障碍树缺失的游戏等场景明确受限。 | 2026-09-14；Apache-2.0。 |
| [Arbigent](https://github.com/takahirom/arbigent) | Kotlin/JVM 桌面 GUI/CLI + Maestro + 模型；场景依赖、YAML、图像断言、设备重连、分片。 | 可复用场景与恢复测试很有价值；桌面安装包不是手机助手。卡住检测是截图像素比较，动画可能影响判断。 | 2026-09-26；Apache-2.0；0.89.0 在 09-25 发布。 |
| [DroidBot](https://github.com/honeynet/droidbot) | 主机 Python/Java/SDK/ADB；随机/脚本探索、UI Transition Graph、可选 CV。 | 可以参考行为探索和转移图；本身不是 LLM 自然语言助手。 | 2026-08-29；MIT。 |
| [AppAgent](https://github.com/TencentQQGYLab/AppAgent) | 主机 Python/ADB + 视觉模型；探索/用户演示生成 App 知识，截图/UI 元素标签、反思。 | 演示转操作经验值得参考；较早研究项目，README 已指向 AppAgentX。原测试集只有 9 App / 45 任务。 | 2025-03-19；MIT。 |

重点技术证据：[AutoGLM 循环](https://github.com/zai-org/Open-AutoGLM/blob/main/phone_agent/agent.py#L136)、[GUI-Owl 真机 runner](https://github.com/X-PLUG/MobileAgent/blob/main/Mobile-Agent-v3.5/mobile_use/run_gui_owl_1_5_for_mobile.py#L170)、[Mobilerun Portal](https://github.com/droidrun/mobilerun/blob/main/docs/guides/device-setup.mdx)、[agent-device 快照规则](https://github.com/callstack/agent-device/blob/main/website/docs/docs/snapshots.md)、[Arbigent 卡住检测](https://github.com/takahirom/arbigent/blob/main/arbigent-core/src/main/java/io/github/takahirom/arbigent/detectStuckScreen.kt)。

## 模型、混合系统和评测

| 项目 | 已核实内容 | 比较边界 | 默认分支提交 / 许可 |
| --- | --- | --- | --- |
| [MAI-UI / Qwen-UI-Agent](https://github.com/Tongyi-MAI/MAI-UI) | 2026-07-30 已加入 Qwen-UI-Agent 后续工作，宣称统一手机、电脑、浏览器、DeepSearch 与 GUI/CLI。 | 新增目录主要为报告/网站入口；旧 MAI-UI 代码另在子目录。项目声明、权重可用性与完整可运行 APK 应分别核实；本文不照抄成绩作为排名。 | 2026-08-19；README 声明 Apache-2.0，第三方组件另计。 |
| [AgentCPM-GUI](https://github.com/OpenBMB/AgentCPM-GUI) | 8B 中英文 Android GUI 模型，截图输入、紧凑 JSON 动作、相对坐标。 | 虽称 on-device，公开 quickstart 展示 CUDA/vLLM；不是可直接安装的手机离线助手。 | 2026-01-11；仓库 Apache-2.0。 |
| [MobiAgent](https://github.com/IPADS-SAI/MobiAgent) | MobiMind 模型、AgentRR record/replay、MobiFlow；有 Android App、ADB runner、手机端推理路线。 | 手机端 README 建议 RAM ≥12GB、Snapdragon 8 Gen 3/8 Elite、Termux/MNN 模型与手动安装；没有证明普通设备普遍即装即用。 | 2026-07-17；仓库 Apache-2.0。 |
| [AndroidWorld](https://github.com/google-research/android_world) | 116 个动态参数任务、20 App；推荐 Pixel 6 / API 33 模拟器、ADB/gRPC；通过数据库/文件验证目标。 | 是评测环境；setup 有 `adb root`，不是普通免 Root 手机助手 APK。 | 2026-09-29；Apache-2.0。 |
| [AndroidLab](https://github.com/THUDM/Android-Lab) | 138 任务、9 App，XML/SoM 两种模式，虚拟设备与成功率/子目标指标。 | App 选型偏离线免登录；Mac 安装文档已有旧 AVD 失效提示。不是日常手机产品。 | 2025-08-18；MIT。 |
| [Memex](https://github.com/memex-lab/memex) | Android/iOS 本地日记与知识库，Agent Skills、工作目录、JS、事件触发和依赖链。 | 邻近的个人数据 Agent；不是系统 GUI 控制器。本地数据存储仍可配云端模型，“local-first”不等于所有推理离线。 | 2026-09-16；GPL-3.0；09-29 Android Early 为预发布。 |

证据：[Qwen-UI-Agent 新工作](https://github.com/Tongyi-MAI/MAI-UI/blob/main/README.md)、[AgentCPM CUDA 示例](https://github.com/OpenBMB/AgentCPM-GUI/blob/main/README.md)、[MobiAgent 手机推理要求](https://github.com/IPADS-SAI/MobiAgent/blob/main/phone_runner/README.md)、[AndroidWorld root setup](https://github.com/google-research/android_world/blob/main/android_world/env/setup_device/setup.py#L162)、[AndroidLab Mac 提示](https://github.com/THUDM/Android-Lab/blob/main/docs/prepare_for_mac.md)。

另核查了 [ClawMate](https://github.com/IPADS-SAI/ClawMate) 与 [MobiInfer](https://github.com/doulujiyao12/mobiinfer)：ClawMate 当前手机路线要求 HarmonyOS NEXT、DevEco 和 HDC，不能列作 Android APK；MobiInfer 是 Android 高通 QNN / HarmonyOS HiAI 推理基础设施，需要对应 SDK、量化模型和硬件支持。两者不计入上述 30 个 Android/相关代表项目。

## 我们的优势

| 维度 | 当前实际实现 | 优势成立的范围 |
| --- | --- | --- |
| 共享 Agent 核心 | APK 内嵌 Chaquopy，调用与桌面相同的 `build_runtime_async`、Agent 服务与 SQLite 事件存储。 | 比只包装聊天请求或仅提供屏幕执行器的方案，统一任务、工具策略和历史更方便；APK 操作系统适配仍需补齐。 |
| 任务恢复和审计 | 持久任务状态；重启把未完成任务标为 interrupted；恢复使用已有历史，要求检查未知结果；审批与出站数据授权留痕。 | 适合长时间编程/研究任务与追踪失败；不是永不中断，也不是其他项目没有恢复能力。 |
| 工作区和研究工具 | 文件读写/补丁、Git、文档/表格、HTTP、记忆、来源与引用工具；手机编辑做摘要校验和原子保存。 | 相对单一手机 GUI runner，工作区任务覆盖更宽；Git/LSP 等工具依赖手机实际存在的可执行文件。 |
| 控制和可观察性 | Workspace/YOLO/Full access；输入/输出/缓存 Token、费率、历史估算；原生完成/失败/审批通知与会话跳转。 | 用户可调整执行政策和费用、观察任务状态；费用不是账单，YOLO 不能绕过 Android 系统权限。 |
| 本地状态与密钥 | 会话和工作区存本机，Android Keystore AES-GCM 保存密钥。 | 自己掌握数据与 API 配置；调用云端模型时，相应上下文仍会出站。 |

本地证据：[mobile_embedded.py](<../../kotlin_app/src/main/python/mobile_embedded.py:94>)、[mobile_task_store.py](<../../mobile_task_store.py:236>)、[mobile_runtime_controller.py](<../../mobile_runtime_controller.py:345>)、[mobile_workspace.py](<../../mobile_workspace.py:174>)、[mobile_usage.py](<../../mobile_usage.py:207>)、[TaskNotifications.kt](<../../kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TaskNotifications.kt:101>)、[EmbeddedSecrets.kt](<../../kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/EmbeddedSecrets.kt:78>)。

## 我们的劣势与已确认漏项

### 1. 当前 APK 没有系统屏幕反馈闭环

Manifest 没有 AccessibilityService、MediaProjection 或系统通知监听服务；未找到专门的 Android UI 树/屏幕采集入口。现有 JS 桥的剪贴板、分享、链接、电量属于 UI 功能，不能算 Agent 已能任意操控其他 App。桌面 BrowserTool 使用 CDP，不是 Android 当前屏幕。

Operit、Zafiro、ClosePaw、PhoneAgent 的源码已有“观察→定位→操作→更新观察”。当前 APK 无法同级覆盖这些系统任务。仅加坐标点击会缺少输入依据和成功验证。

证据：[AndroidManifest.xml](<../../kotlin_app/src/main/AndroidManifest.xml:5>)、[NativeJsBridge.kt](<../../kotlin_app/src/main/kotlin/com/agentworkspace/mobile/bridge/NativeJsBridge.kt:90>)、[browser.py](<../../../src/agent_workspace/tools/browser.py:293>)。

### 2. APK 与 Termux 的能力被不同启动路径分开

`entrypoint.py:31` 对 Chaquopy 和 `apply_android_patches()` 二选一。当前 APK 的 `install_android_runtime()` 替换密钥存储和线程执行器；Termux 路径才替换 POSIX 终端、注册 Termux:API 和 rish/Shizuku。Termux 中现有的点击、滑动、输入、按键和清应用数据工具，没有在 APK 这条路径注册。

服务和 Bootstrap 的类名仍有 Termux 字样，但当前 APK 装的是源码和 Chaquopy 依赖，并非完整 Termux/Linux 工具链。比较和说明应以实际运行方式为准。

证据：[entrypoint.py](<../../entrypoint.py:31>)、[chaquopy_runtime.py](<../../android_adapter/chaquopy_runtime.py:139>)、[patcher.py](<../../android_adapter/patcher.py:47>)、[shizuku.py](<../../android_adapter/shizuku.py:84>)、[TermuxBootstrap.kt](<../../kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxBootstrap.kt:8>)。

### 3. 共享注册表暴露了 Android 不可用的工具

标准注册表仍暴露 `run_terminal` 和 `speak_text`，平台可用性未在模型工具列表中筛掉。`run_terminal` 执行落到 `_conpty_sync`，明确拒绝非 Windows；`speak_text` 也明确仅支持 Windows。这是已确认的工具适配缺口。

并非所有命令都不能执行：`run_process` 的 direct 子进程路径和 `run_sandbox` 的 POSIX 路径仍存在。其实际可用性取决于 APK 的可执行文件、权限和设备环境，应做真机能力探测，而不是由“工具已注册”推断可用。

证据：[registry.py](<../../../src/agent_workspace/tools/registry.py:116>)、[pty.py](<../../../src/agent_workspace/tools/pty.py:293>)、[voice.py](<../../../src/agent_workspace/tools/voice.py:109>)、[command.py](<../../../src/agent_workspace/tools/command.py:214>)、[host_staged_sandbox.py](<../../../src/agent_workspace/tools/host_staged_sandbox.py:366>)。

### 4. MCP/自定义扩展的手机授权链未接通

手机启动 `build_runtime_async` 只提供工具和模型出站授权回调，没有提供 `extension_approval_callback`。工作区配置 MCP/custom tools 后，默认运行时可能抛 `ExtensionApprovalRequiredError`。底层模块存在不能等同手机扩展已经完整可用。

证据：[entrypoint.py](<../../entrypoint.py:120>)、[runtime.py](<../../../src/agent_workspace/application/runtime.py:605>)。

### 5. 手机自动化、后台调度和跨设备工作较弱

核心已加载工作区定时配置并启动 scheduler，不能说完全没有定时任务；但当前手机没有调度管理页面、AlarmManager/WorkManager 或开机恢复。服务使用 `START_NOT_STICKY`、一小时 WakeLock，并在系统 timeout 时停止。现有完成通知不等于系统事件触发或长期无人值守执行。

当前 APK 仅绑定 loopback。没有 Paseo/CC Pocket 那种完整设备配对、主机发现、断网排队与手机/电脑接力产品流程。语音输入、原生助手入口、widget 等也落后 AndCode/AndroidHarness。

证据：[runtime.py](<../../../src/agent_workspace/application/runtime.py:598>)、[TermuxDaemonService.kt](<../../kotlin_app/src/main/kotlin/com/agentworkspace/mobile/embedded/TermuxDaemonService.kt:47>)、[mobile_embedded.py](<../../kotlin_app/src/main/python/mobile_embedded.py:94>)。

### 6. 没有内置手机模型推理和可比较的任务成功率

Ollama Adapter 调用已有 HTTP `/api/chat` 服务，当前 APK 没有内置 Android 模型加载、量化或 GPU/NPU 推理。Operit 的 MNN/llama.cpp、MobiAgent 的手机推理路线可以参考，但设备资源和支持范围需要单独评估。代码见 [ollama.py](<../../../src/agent_workspace/providers/ollama.py:47>)。

既有 Python/UI/实机测试和 256 状态布局检查是工程验证。缺少固定 App/版本/设备、可判定终态的系统任务集，以及成功率、步骤、时延、费用、重试和接管次数的对比数据。因此不能宣称总体 Agent 效果优于任何竞品。

## 建议优先级

| 顺序 | 工作 | 验收依据 |
| --- | --- | --- |
| 1 | 统一 APK/Termux 工具能力；实现或隐藏不可用终端/TTS，接通扩展授权；提供手机端 doctor 与能力报告。 | 真机上被模型看到的工具都有可运行的最小验证；无支持条件的工具返回明确原因；测试覆盖 APK 实际启动路径。 |
| 2 | 建立 Android 观察与操作桥：App/activity、UI 树、截图、屏幕尺寸、快照版本、typed actions、动作后刷新与目标验证。 | 过期节点引用拒绝执行；横屏/展开后坐标重新绑定；无树界面有截图兜底；失败可暂停接管。参考 Zafiro、Operit、agent-device。 |
| 3 | 建立 20–30 个可复现真实手机任务，先覆盖读信息、搜索、表单、文件和多 App 传递等流程。 | 固定设备/App 版本、模型、预算与重试政策；每任务有明确终态；分别报告成功、步骤、时延、Token、费用和人工接管。 |
| 4 | 完善手机调度和日常入口：调度页、系统调度器、后台恢复状态、语音、assistant/widget、通知内操作。 | 锁屏、进程退出、重启、权限拒绝、通知关闭均有清楚行为；不承诺系统限制下永远常驻。参考 AndCode、AndroidHarness。 |
| 5 | 增加桌面/手机设备配对、远程工作区、任务接力与断网队列。 | 身份与权限绑定到设备/主机；重连后消息去重和状态恢复；数据保存位置可见。参考 Paseo、CC Pocket。 |
| 6 | 在上述执行与评测基础上，评估可选本地模型和可复用 App 流程。 | 明确设备兼容表、首 Token/每秒速度、内存、电量和成本；本地/远程路由可见；重复流程能验证前置状态后再复用。 |

若定位是“手机编程工作台”，优先顺序 1、3、4、5；若定位是“安卓系统助理”，优先顺序 1、2、3、4。两种定位都可以复用现有持久任务、审批与模型接口。

## 许可与名称核验

- Operit 当前是 LGPL-3.0；RikkaHub 是 AGPL-3.0；BotDrop/Memex 是 GPL-3.0；不能把所有 GitHub 项目统一称为宽松许可。
- OpenGUI 核心/Android client 为 BSL 1.1，变更日期 2030-04-29 转 Apache-2.0；DSH 等部分插件自身为 MIT。OmniBot LICENSE 有附加限制，不能只按 AGPL 标签判断。
- Paseo API 元数据为 `NOASSERTION`，已读取 LICENSE 正文确认主体 Apache-2.0。PhoneAgent 也以 LICENSE 正文为依据。
- DroidClaw 原版未发现根 LICENSE，Kira JS 许可不等于 companion APK 许可。模型权重、训练数据、第三方依赖和云服务需要分别确认。
- 阿里系列是 `X-PLUG/MobileAgent`；`alibaba/MobileAgent` 查询返回 404。AutoGLM 是另一个项目。
- `droidrun/droidrun` 已转到 `droidrun/mobilerun`；AndroidLab 正式路径为 `THUDM/Android-Lab`。
- `vvtech-ai/PhoneAgent` 是 SIP/AI 电话项目，不是这里讨论的 Android GUI 控制器；`evania-maker/PhoneAgent` 为衍生仓库，本文采用原作者 `MR-MaoJiu/PhoneAgent`。
