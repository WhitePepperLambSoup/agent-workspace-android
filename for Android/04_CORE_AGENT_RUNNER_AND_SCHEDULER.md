> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android (Termux) 核心运行时与后台调度保活方案

> 文档编号：AW-AND-04  
> 涉及模块：`src/agent_workspace/application/runner.py`、`core/scheduler.py`、`core/prompt_assembly.py`、`application/background_jobs.py`  

---

## 1. 核心认知循环 (Agent Runner) 的纯度分析

### 1.1 零改动复用结论
经全面静态审计，本项目的核心大脑子系统：
* [`application/runner.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/application/runner.py)（Agent 执行状态机与工具调用回退逻辑）
* [`core/prompt_assembly.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/core/prompt_assembly.py)（前缀缓存严格对齐的系统提示词装配）
* [`core/compaction_strategies.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/core/compaction_strategies.py)（上下文动态修剪与模型摘要生成）
* [`core/token_budget_arbiter.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/core/token_budget_arbiter.py)（严格的单轮与累计 Token 配额仲裁）
* [`providers/`](file:///d:/opencode%20program/Agent/src/agent_workspace/providers/)（OpenAI、Anthropic、Gemini、Ollama、DeepSeek 适配器）

**全部为 100% 纯 Python 异步逻辑，不依赖任何特定操作系统的专有二进制或库**。在 Termux 的 Python 3.12 下无需做任何代码修改，直接全功能运行。

---

## 2. 移动端 ARM 架构与内存约束优化

虽然 Android 旗舰机普遍配备 12GB~16GB 内存，但单个 Linux 进程若常驻内存超过 300MB+，极易被 Android 系统的低内存杀手（Low Memory Killer, LMK）在后台优先清理。

### 2.1 针对移动端的资源微调策略

1. **垃圾回收的主动干预**：
   在长上下文压缩（Compaction）和大规模文件读取（如读取 10MB+ 的 PDF 或长日志）完成后，主动触发 Python 的代际垃圾回收：
   ```python
   # 在 runner.py 的每次 turn 结算后
   import gc

   gc.collect(generation=1)
   ```
2. **文本分片与流式缓存控制**：
   限制工具输出日志在内存中的常驻大小（已通过 `tools/policy` 中的 `max_output_bytes` 约束为 64KB），避免模型单次接收超大上下文爆内存。
3. **SQLite 内存缓存收敛**：
   在 Termux 中初始化 SQLite 连接时，微调 `cache_size`：
   ```sql
   PRAGMA cache_size = -4000; -- 限制 SQLite 页面缓存占用不超过 4MB
   PRAGMA temp_store = MEMORY;
   ```

---

## 3. 应对 Android Doze（打盹模式）的调度与保活机制

### 3.1 移动端后天休眠的挑战
在 Windows 桌面端，`scheduler.py` 通过标准的 `asyncio.sleep()` 或线程 Timer 触发定时任务。但在 Android 手机上：
* 屏幕熄灭 3 分钟后，系统进入轻度打盹；
* 屏幕熄灭 15 分钟后，系统进入深度打盹（Deep Doze），**挂起所有应用 CPU 时钟中断，彻底断开 Wi-Fi/蜂窝连接**。
* 普通的 `asyncio.sleep()` 会随之被冻结，直到用户重新点亮手机屏幕才会猛然苏醒，导致定时任务严重失真。

### 3.2 Termux 下的三级保活解决方案

```
                  ┌─────────────────────────────────┐
                  │      Termux 运行时保活总控       │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
   [ 一级：CPU 唤醒锁 ]       [ 二级：前台通知常驻 ]    [ 三级：网络降级与断线重试 ]
  termux-wake-lock 持有      通知栏显示 Agent 状态       模型请求 exponential backoff
  阻止系统休眠 CPU           防止 OOM Killer 杀进程     适应手机切基站与弱网抖动
```

#### 1. 唤醒锁常驻 (Partial WakeLock)
在 Agent 启动或有定时任务注册时，通过 Termux 命令获取系统内核唤醒锁：
```python
import subprocess
import shutil


def acquire_android_wakelock() -> bool:
    if shutil.which("termux-wake-lock"):
        subprocess.run(["termux-wake-lock"], check=False)
        return True
    return False


def release_android_wakelock() -> None:
    if shutil.which("termux-wake-unlock"):
        subprocess.run(["termux-wake-unlock"], check=False)
```

#### 2. 移动蜂窝/Wi-Fi 切换时的网络弹性增强
手机在移动过程中极易发生 Wi-Fi 到 5G 的切换（导致 TCP 连接瞬间重置）。在 `providers/` 的 HTTP 请求调用链中：
* 为 `httpx.AsyncClient` 默认配置 `transport = httpx.AsyncHTTPTransport(retries=3)`；
* 针对 `httpx.ConnectError` 和 `httpx.NetworkError` 增加 1s, 2s, 4s 的指数退避重试，确保不会因为进电梯或基站切换导致整个多轮 Agent 任务崩溃。
