> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android (Termux) 移植分步实施与落地路线图

> 文档编号：AW-AND-07  
> 核心原则：小步快跑、无侵入式改造，优先保证 Windows/Linux 双向代码兼容，绝不破坏现有测试资产。

---

## 阶段规划甘特视图

```
[阶段 1] 跨平台抽象层抽取 (1-2 天)
  ├─ 凭据层 CredentialStore 抽象与 POSIX 0600 实现
  ├─ 进程管理 ProcessSupervisor 抽象与 POSIX 进程组实现
  └─ 终端 PTY 抽象与 POSIX pty.openpty() 实现
  
[阶段 2] Termux 自举打包与真机打通 (1 天)
  ├─ 编写 packaging/termux/bootstrap.sh
  ├─ 验证 Termux ARM64 依赖安装与 prebuilt 库
  └─ 跑通 agent-workspace CLI 基础命令与单测
  
[阶段 3] 移动端 Web 伴侣交互升级 (2-3 天)
  ├─ 优化 serve_api.py 移动端响应式布局与软键盘避让
  ├─ 移植轻量移动端行内 Diff 与 Markdown 渲染
  └─ 配置 PWA 支持（添加到主屏幕）
  
[阶段 4] Android 专有增强与安全铁律 (2 天)
  ├─ 接入 Termux:API (剪贴板、通知、电池感知)
  ├─ 接入 Shizuku (rish 免 Root 系统命令桥接)
  └─ 固化 ASK 模式安全审批铁律
```

---

## 详细实施步骤与验证准则

### 阶段 1：跨平台抽象层抽取（在主干代码库中完成）

#### 1.1 改造 `src/agent_workspace/credentials.py`
* **改动点**：
  * 定义标准 `CredentialStore` 协议；
  * 保留现有 Windows DPAPI 为 `WindowsCredentialStore`；
  * 新增 `PosixFileCredentialStore`（基于 AES-GCM + 0600 权限）；
  * 在模块顶层增加自动探测工厂：
    ```python
    def get_default_credential_store() -> CredentialStore:
        if sys.platform == "win32":
            return WindowsCredentialStore()
        return PosixFileCredentialStore()
    ```
* **验证**：在 Linux/POSIX 环境下运行 `pytest tests/test_credentials.py` 全部通过。

#### 1.2 改造 `src/agent_workspace/tools/process_runner.py` 与 `pty.py`
* **改动点**：
  * 通过 `sys.platform` 分支隔离 `win32api` 和 `ConPTY` 调用；
  * 非 Windows 环境下加载 `pty_posix.py` 和 `posix_process_runner.py`。
* **验证**：在非 Windows 环境下能够正常拉起 Bash，并通过信号向进程组发送 `SIGKILL` 终止多级子进程。

---

### 阶段 2：Termux 真机环境打通

#### 2.1 部署自举脚本
* 将 `packaging/termux/bootstrap.sh` 推送到手机 Termux 环境中执行：
  ```bash
  bash bootstrap.sh
  ```
* 验证输出包含：
  ```text
  [✓] Agent Workspace bootstrap completed successfully!
  ```

#### 2.2 CLI 冒烟测试
* 在 Termux 中执行：
  ```bash
  # 1. 配置模型 Profile
  agent-workspace providers set deepseek --name DeepSeek \
    --protocol openai-compatible --base-url https://api.deepseek.com/v1 \
    --model deepseek-chat --api-key-env DEEPSEEK_API_KEY --default

  # 2. 诊断环境与工作区
  agent-workspace doctor --profile deepseek --workspace .

  # 3. 运行一次实际代码审查任务
  agent-workspace run "请阅读当前目录的 pyproject.toml 并分析依赖项" --profile deepseek
  ```
* **验收标准**：CLI 能够流式输出思考与正文，无任何跨平台崩毁异常。

---

### 阶段 3：移动端 Web 伴侣交付 (`serve_api.py`)

#### 3.1 增强移动前端样式与事件流
* 重构 `serve_api.py` 的 HTML/CSS/JS 模板，引入响应式视口：
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  ```
* 增加移动端触控优化的审批按钮浮层（Approve / Reject）。

#### 3.2 启动与真机体验
* 在 Termux 运行：
  ```bash
  agent-workspace serve --host 127.0.0.1 --port 8080
  ```
* 打开手机 Chrome 访问 `http://127.0.0.1:8080/console`；
* 点击 Chrome 菜单 -> “添加到主屏幕”；
* **验收标准**：从桌面图标点开，界面全屏沉浸呈现，能够在手机键盘上输入指令、查看代码 Diff 并完成工具审批。

---

### 阶段 4：系统级增强扩展落地（可选）

1. **验证 Termux:API**：
   * 在手机端执行 `agent-workspace` 工具调用，成功弹出手机系统通知栏提示，并可读取剪贴板内容。
2. **验证 Shizuku 桥接**：
   * 运行配对 Shizuku，授权 Termux 后，执行 `pm clear` 清理测试用 App 缓存。
   * 验证 `WorkspacePolicy` 能够精准拦截高危系统调用并强行要求用户审批。

---

## 最终产物清单

完成上述路线图后，本项目将形成一套完整的跨端工程矩阵：
* **Windows 桌面端**：保持原有的高集成度工作台；
* **Linux/服务器端**：保持无缝的后台 CLI 与自动化调度服务；
* **Android 移动端**：以 Termux 为基座，拥有极速的本地代码编辑能力与优雅的自适应 Web 伴侣界面。
