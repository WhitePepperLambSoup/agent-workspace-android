> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android 原生应用 (Kotlin + Jetpack Compose) 架构与移植规范

> 文档编号：AW-AND-08  
> 目标：如果放弃 Termux 脚本模式，采用正规 Android 原生应用（APK 安装包）形态，阐述基于 **Kotlin** 的架构设计与工程落地路线。

---

## 1. 概念澄清：Termux 方案 vs Kotlin 原生 APK 方案

在讨论语言之前，必须理清两种截然不同的形态定位：

| 维度 | **Termux 方案 (上一方案)** | **Kotlin 原生 APK 方案 (本方案)** |
|---|---|---|
| **形态本质** | Android 上的 Linux 终端虚拟环境 | 正规 Android 应用安装包 (`.apk`) |
| **主导语言** | **Python 3.12 + Shell** | **Kotlin 2.0+ + Jetpack Compose** |
| **安装方式** | 先装 Termux，在里面敲命令行启动 | 直接下载 APK 点击安装，桌面出独立图标 |
| **界面形态** | 终端命令行 (TUI) 或 浏览器 Web 控制台 | **100% Android 原生 UI（质感与流畅度顶级）** |
| **工具链支持** | 可以在手机本地直接跑 `git`、`pytest` 等命令 | **无法在手机本地执行编译**，重在移动控制与端云联动 |

---

## 2. Kotlin 原生方案的核心抉择：那 7.2 万行 Python 代码怎么办？

如果决定使用 **Kotlin** 开发 Android 原生应用，会面临两个架构抉择：

### 路线 A：Kotlin 原生外壳 + 嵌入式 Python 引擎 (Chaquopy / JNI)【推荐落地】
* **架构模式**：
  * **Kotlin 负责原生体验**：UI 界面、前台保活服务（ForegroundService）、Android KeyStore 密钥管理、手机传感器、Shizuku 官方 AIDL 绑定、通知栏交互；
  * **Python 负责 Agent 认知大脑**：保留原项目的 `application/runner.py`、`core/prompt_assembly.py`、`providers/` 等核心纯 Python 代码，通过 **Chaquopy**（官方 Android Python 嵌入框架）打进 APK 内；
  * **沟通方式**：Kotlin 通过 Java/Python JNI 互相调用数据。
* **优点**：既拥有了 Kotlin 顶级的原生 App 质感，又避免了重写 7.2 万行 Python 算法与模型协议。

### 路线 B：100% 全盘纯 Kotlin 重写 (Pure Native)【极致但工程量巨大】
* **架构模式**：彻底淘汰 Python，将整套 Agent 逻辑重构为 Kotlin：
  * 异步模型：`asyncio` -> **Kotlin Coroutines (`suspend fun`) & Flow**
  * 网络请求：`httpx` -> **Ktor / OkHttp 3**
  * 数据库：`sqlite3` -> **Android Room (SQLite) / SQLDelight**
  * 界面：PySide6 -> **Jetpack Compose (Material You)**
  * 序列化：`json / jsonschema` -> **kotlinx.serialization**
* **优点**：性能极强、零 Python 内存开销、冷启动毫秒级、包体积可压到 20MB 以内。
* **代价**：需要至少 2~3 个月将全部协议、前缀缓存算法与事件流用 Kotlin 重写一遍。

---

## 3. 推荐路线 A 的 Kotlin 系统架构蓝图

```
┌─────────────────────────────────────────────────────────────┐
│              Android 原生层 (100% Kotlin)                    │
├─────────────────────────────────────────────────────────────┤
│  [ UI 交互层 ]                                              │
│  - Jetpack Compose (Material You, 动态色彩主题, 触控滑动)    │
│  - Markdown 渲染 (Compose-Markdown)                         │
│  - 行内 Diff 视图 (HorizontalScrollable Compose Canvas)     │
│                                                             │
│  [ 系统级服务层 ]                                           │
│  - AgentForegroundService (持有 WakeLock, 保持长时间思考不被杀)│
│  - AndroidKeyStoreManager (硬件级 TEE 加密保存 API Key)      │
│  - ShizukuServiceConnection (绑定 Shizuku AIDL 获得 ADB 权限)│
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               │ JNI (Chaquopy 调用)           │ AIDL
               ▼                              ▼
┌──────────────────────────────┐┌──────────────────────────────┐
│  Python 核心引擎 (嵌入 APK)  ││   Android 系统特权执行面    │
│  - AgentRunner               ││  - 清理 App 缓存 (pm clear) │
│  - EventStore (SQLite WAL)   ││  - 修改系统设置 (Settings)  │
│  - Model Providers           ││  - 模拟屏幕点击 (Input tap) │
└──────────────────────────────┘└──────────────────────────────┘
```

---

## 4. 关键 Kotlin 核心组件代码结构

在 `for Android/kotlin_app/` 目录下，我们构建了以下原生模块骨架：

1. **`AgentService.kt`**：Android 原生前台保活服务，挂载通知栏状态机，防止锁屏被杀；
2. **`PythonBridge.kt`**：Kotlin 与 Python 核心引擎的 JNI 双向通道；
3. **`TimelineView.kt`**：基于 Jetpack Compose 的现代化对话与思考折叠流；
4. **`MainActivity.kt`**：单 Activity 原生入口与边缘到边缘（Edge-to-Edge）沉浸式显示。
