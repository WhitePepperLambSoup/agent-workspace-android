# Android Agent 双宿主增强设计

- 日期：2026-09-22
- 状态：已获用户批准，待实现计划评审
- 范围：Android Termux 宿主与独立 APK 宿主
- 目标平台：Android 10-15，ARM64-v8a，无 Root

## 1. 背景与目标

Windows 端 Agent 已基本可用。Android 端需要结合移动设备的生命周期、权限、后台执行、网络和电量约束，形成可长期运行的移动 Agent 体验。

本设计采用“双宿主、共享 Android 核心”方案：

- Termux + 移动 Web 控制台继续作为完整工具链宿主。
- 独立 APK 使用 Kotlin 前台服务、WebView 和内置运行时。
- 两种宿主共用移动 Gateway 协议、任务状态模型、事件游标和移动 Web UI。
- Python Agent 核心继续复用，但 Android 只通过 `for Android/` 内的运行时补丁接入。

首轮重点保证：

1. 手机端对话与连续任务。
2. 锁屏和前后台切换下的后台长任务。
3. 剪贴板、通知、电池、文件选择、分享、Termux:API 和 Shizuku 等移动系统能力。

代码工作区、弱网与省电、独立 APK 的安装初始化也必须在架构上预留，而不是后续临时拼接。

## 2. 强制隔离边界

Android 改造必须与 Windows 端源代码隔离：

- 新增或修改的 Android 代码、脚本、资源、测试和文档优先放在 `for Android/`。
- 不修改 `desktop/`。
- 不修改 `src/agent_workspace/` 中的 Windows 实现、Windows UI、Windows 构建逻辑或通用核心行为。
- 不修改现有 Windows 测试以适配 Android。
- `for Android/` 可以读取和打包 `src/agent_workspace/`，但不得为了 Android 需求直接改写主干源码。
- Android 专属测试必须验证 Windows 文件集合没有被改动；实现前后使用受限路径 diff 检查。
- Git 提交只包含本次 Android 设计或实现所需的明确文件，不带入现有工作树的其他未提交变更。

## 3. 总体架构

```text
移动 Web 控制台 / APK WebView
            │
            ▼
Android Mobile Gateway
  - 本地 HTTP API
  - 任务提交与恢复
  - SSE 事件流
  - 断线重连与游标续传
            │
            ▼
Android Runtime Controller
  - 启动、停止、重启状态机
  - 后台任务监督
  - WakeLock / 通知状态
  - 崩溃恢复
            │
            ▼
现有 Python Agent Runtime
  - 通过运行时补丁接入 Android
  - 不修改 Windows 源码
```

### 3.1 宿主职责

Termux 宿主：

- `entrypoint.py` 启动 Android Runtime Controller 和 Mobile Gateway。
- 使用 POSIX 进程组、Termux WakeLock 和 Termux:API。
- 使用当前 Android 适配器替换凭据、PTY、进程管理和系统能力。
- 保留 CLI 能力，移动 Web 控制台作为推荐交互层。

独立 APK 宿主：

- `WebUiActivity` 负责 WebView、文件选择器、页面重连和生命周期观察。
- `TermuxDaemonService` 负责前台服务、Python 进程托管、通知、WakeLock 和异常重启。
- `TermuxBootstrap` 负责资产校验、原子初始化、版本切换和回滚。
- Native JS Bridge 负责震动、剪贴板、分享、外部链接和电量读取。
- APK 不在 Kotlin 中实现 Agent 业务逻辑，避免与 Python runtime 分叉。

两种宿主都通过同一 Mobile Gateway 协议与移动 UI 通信。

## 4. Runtime 与任务生命周期

Activity、WebView、浏览器都不是任务的拥有者。Runtime Controller 才是任务拥有者；UI 只是观察者。

Runtime 状态：

```text
STOPPED
  -> STARTING
  -> READY
  -> RUNNING
  -> PAUSED_BY_SYSTEM
  -> RECOVERING
  -> FAILED
```

任务状态：

```text
queued -> running -> waiting_approval -> succeeded
                                  ├── failed
                                  ├── cancelled
                                  └── interrupted
```

每个任务必须有持久化的任务 ID、会话 ID、当前状态、最后事件序号和恢复信息。重要状态写入已有事件存储，不能只依赖 Kotlin 内存或浏览器状态。

### 4.1 Android 专属 Gateway API

```text
POST /mobile/tasks
GET  /mobile/tasks/{task_id}
POST /mobile/tasks/{task_id}/cancel
GET  /mobile/tasks/{task_id}/events?after=<sequence>
GET  /mobile/capabilities
GET  /mobile/health
```

任务提交立即返回：

```json
{
  "task_id": "...",
  "session_id": "...",
  "state": "queued",
  "last_sequence": 123
}
```

现有 `/sessions/{id}/run` 保留兼容，但 Android 新 UI 使用异步任务接口，避免长时间 HTTP 请求绑定前台页面。

### 4.2 事件流与重连

- 使用 SSE 传递事件。
- 前端保存每个会话的最后一个 `sequence`。
- 断线重连时带上 `after`，只获取缺失事件。
- 服务端必须保证事件按序发送。
- 前端重复收到事件时按事件 ID 或序列号去重。
- 前端重连不得重新提交任务。
- 审批请求、工具失败、任务完成、任务失败、任务取消和未知状态属于必须送达事件。

### 4.3 异常恢复

Activity 被回收时：

- 任务继续运行。
- 任务完成、失败或需要审批时由通知栏提示。
- 重新打开界面后按游标恢复时间线。

Python 进程被杀或手机重启时：

- 启动时扫描未结束任务。
- 已明确结束的任务恢复最终状态。
- 工具调用处于未知状态时标记为 `interrupted` 或 `unknown`。
- 有副作用的工具调用不得自动重放。
- UI 提供“恢复任务”或“重新开始”，由用户明确选择。

Provider 网络失败时：

- 保留本地任务和事件。
- 使用有上限的指数退避。
- 网络恢复后继续请求或报告不可恢复错误。
- 不因浏览器连接断开而取消任务。

## 5. Android 后台执行与电量策略

Kotlin 前台服务负责：

- 保证同一时刻只有一个 Python Agent 进程。
- 读取并限制子进程日志，避免无限增长。
- 监督 Python 进程退出。
- 使用指数退避重启，防止崩溃重启风暴。
- 更新通知栏中的 Runtime 和当前任务状态。
- 只在有运行任务或待执行队列时申请 WakeLock。
- 任务结束或暂停后释放 WakeLock。

服务模式：

```text
INTERACTIVE  前台页面正在使用
TASK_RUNNING 后台任务运行中，保持 WakeLock
BATTERY_SAVER 暂停后台调度，不持有 WakeLock
```

通知栏动作：

- 打开 Agent。
- 取消当前任务。
- 重启引擎。
- 查看诊断信息。

Termux 宿主使用 `termux-wake-lock` / `termux-wake-unlock`，APK 宿主使用 Android `PARTIAL_WAKE_LOCK`。两者的任务状态语义必须一致。

低电量、Doze、后台限制和厂商省电策略只影响调度和保活，不得静默丢失任务。UI 必须告知用户当前系统限制及其影响。

## 6. 移动交互设计

移动 Web 和 WebView 使用移动优先的三层布局：

```text
顶部：当前会话、运行状态、连接状态
中部：可滚动事件时间线
底部：快捷操作、审批区域、输入框
```

功能要求：

- SSE 实时更新事件，不等待同步 `/run` 请求。
- 工具调用使用可折叠卡片，显示等待、运行、成功、失败、未知状态。
- 审批请求固定在底部审批区域，不要求用户在时间线中寻找。
- 会话切换使用抽屉或底部面板。
- 输入框支持软键盘避让、自动增高、草稿保存和发送中取消。
- 触控目标不小于 44dp。
- 使用 `safe-area-inset` 处理刘海、手势导航条和横屏。
- 不使用 `prompt()` 和原生 `alert()` 作为主要交互。
- 支持复制、系统分享、文件选择和震动反馈。
- 断线时保留页面状态，并从最后事件序号继续同步。
- 代码工作区采用单文件浏览、搜索和 Diff 查看，不复制 Windows 多栏布局。

低频功能放入底部面板：

```text
会话管理
任务历史
代码工作区
设备能力
运行诊断
设置
```

## 7. 系统能力与权限模型

Gateway 提供统一能力清单：

```json
{
  "termux_api": "available",
  "shizuku": "permission_required",
  "notifications": "available",
  "battery": "available",
  "file_picker": "available",
  "screen_actions": "unavailable"
}
```

能力状态只能取以下值：

```text
available
permission_required
dependency_missing
denied
degraded
unavailable
```

能力边界：

- Termux:API：剪贴板、通知、电池和设备信息。
- Shizuku：应用管理、系统设置和屏幕动作。
- APK Native Bridge：震动、剪贴板、分享、文件选择器和外部链接。
- Android Notification：后台任务开始、审批、完成、失败和恢复提示。
- 电池状态：低电量时提示用户切换省电模式，不直接停止任务。
- 网络状态：断网时暂停新的 Provider 请求，保留本地任务和事件。

系统级和破坏性能力默认要求显式审批。审批详情必须展示完整包名、路径、命令和影响范围。Shizuku 未授权时不得绕过权限模型或偷偷使用其他高权限通道。

Android 默认只绑定 loopback，不开放局域网访问。文件操作默认限制在用户选择的工作区。

## 8. 存储、安全与凭据

三类数据分开保存：

```text
运行数据：SQLite、事件、任务队列
凭据数据：模型 API Key、服务 Token
用户数据：工作区文件、导入导出文件
```

Termux：

- SQLite、事件库和任务队列放在 Termux 私有目录。
- 凭据使用 Android 适配层的 POSIX 权限和加密凭据库。
- 共享存储只通过用户主动选择访问。

APK：

- 运行数据放在应用私有目录。
- 凭据使用应用私有目录，并由 Android Keystore 包装本地密钥。
- 服务 Token 不写入 Web 资源或普通日志。
- 日志、诊断和导出自动脱敏 API Key、Bearer Token、Cookie、环境变量和用户路径。

## 9. APK 初始化、更新与资产校验

APK 初始化必须是可回滚的原子流程：

```text
读取资产清单
  -> 校验 SHA-256
  -> 解压到 staging 目录
  -> 校验 Python / entrypoint / 依赖
  -> 原子切换 active 目录
  -> 写入版本标记
```

失败时保留旧版本，不留下半初始化状态。

安装标记至少包含：

```text
应用版本
Agent 代码版本
Web UI 版本
Rootfs 版本
CPU ABI
文件哈希
```

构建规则：

- 没有真实可执行的 ARM64 rootfs 时构建必须失败。
- 禁止自动生成 placeholder rootfs 并继续生成 APK。
- 资产阶段必须校验 Python、入口脚本、依赖和 ABI。
- 当前只支持真实验证过的 ARM64-v8a；未准备对应 rootfs 时不得宣称支持 `armeabi-v7a` 或 `x86_64`。
- 不通过降低 target SDK 或隐藏错误规避 Android 运行时限制。

## 10. 运行诊断

移动端提供只读诊断页，显示：

- 宿主类型：Termux 或 APK。
- Runtime 状态和任务状态。
- Python 可执行文件路径。
- Agent、Web UI、Rootfs 版本。
- ABI、Android 版本和设备信息。
- API 端口与本地连接状态。
- 电池、网络和通知权限状态。
- Termux:API 与 Shizuku 状态。
- 最近启动失败原因。
- 最近任务和恢复状态。
- 脱敏日志导出入口。

诊断页不能直接执行任意系统命令。

## 11. 测试与验收

所有 Android 专属 Python 测试放在 `for Android/` 或现有 Android 测试入口；Kotlin 单元测试和设备测试放在 `for Android/kotlin_app/`。不修改 Windows 测试来迁就 Android。

Python 侧必须覆盖：

- 异步任务提交、查询和取消。
- SSE 游标续传、去重和断线恢复。
- 前端断开后任务继续运行。
- Python 进程重启后的任务恢复。
- 未知工具调用不自动重放。
- Termux:API / Shizuku 缺失时降级。
- loopback 和 Token 访问控制。
- 敏感信息日志脱敏。
- 占位 rootfs、错误 ABI 和损坏资产拒绝。
- 任务队列和事件的原子恢复。

Kotlin 侧必须覆盖：

- Bootstrap 路径穿越防护。
- 初始化失败回滚。
- 服务重复启动不会产生多个 Python 进程。
- Python 进程异常退出后的退避重启。
- WakeLock 只在任务期间持有。
- 通知权限缺失时任务仍可执行。
- Activity 销毁不影响后台任务。
- WebView 重连不重复提交任务。
- Native Bridge 拒绝非 HTTP/HTTPS 外部链接。

真机验收至少覆盖一台 ARM64 设备：

1. 首次安装与初始化。
2. Termux 模式启动。
3. APK 模式启动。
4. 正常对话与流式输出。
5. 超过 5 分钟的后台任务。
6. 锁屏后任务继续。
7. Activity 被杀后重新打开。
8. Python 子进程异常退出后恢复。
9. 网络断开与恢复。
10. 低电量状态。
11. 通知权限拒绝。
12. Termux:API 未安装。
13. Shizuku 未授权。
14. 任务审批与取消。
15. 异常后的诊断信息。

验收指标：

- 任务只提交一次，不因重连重复执行。
- 重连后事件无重复、无遗漏。
- 后台任务完成或失败后可收到通知。
- Activity 回收不影响后台任务。
- 破坏性系统能力不能绕过审批。
- 无真实 rootfs 时构建明确失败。
- Windows 相关源码和测试文件无差异。

## 12. 分阶段实现顺序

1. 在 `for Android/` 内建立 Mobile Gateway、任务状态和事件游标测试。
2. 接入 Runtime Controller 与 Termux 宿主生命周期。
3. 接入 APK 前台服务、进程监督、通知和 WakeLock 状态机。
4. 将移动 Web / WebView 改为异步任务、SSE、断线续传和审批优先交互。
5. 完善能力清单、Termux:API、Shizuku、文件选择和 Native Bridge。
6. 完善移动代码工作区、Diff 和弱网/省电策略。
7. 完成 APK 原子初始化、真实 rootfs 校验、资产版本和回滚。
8. 运行 Android 专属测试、Windows 受限 diff 检查和真机验收。

实现阶段不得为了绕过隔离边界而修改 Windows Agent 源码；若发现通用核心缺少 Android 必需接口，先在 `for Android/` 内用适配器或包装层解决，并将需要主干变更的事项单独记录为后续提案。
