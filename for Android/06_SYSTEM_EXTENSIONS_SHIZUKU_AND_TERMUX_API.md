> 历史方案说明：本页保留早期 Termux/原生宿主设计供参考。当前默认 APK 使用 Chaquopy Python 3.12、CPU JNI 推理和可选 PRoot 工具链；旧页的全功能/后台保活/默认工具可用性描述不是当前验收结论。安装与构建请以 [README](README.md)、[当前架构](00_PORTING_OVERVIEW_AND_ARCHITECTURE.md) 和 [构建指南](10_APK_BUILD_AND_RELEASE_GUIDE.md) 为准。

# Android 系统级扩展：Termux:API 与 Shizuku 深度集成规范

> 文档编号：AW-AND-06  
> 目标：打破沙盒边界，让 Agent 获得手机系统级操作能力（通知、剪贴板、ROM 垃圾清理、系统设置修改、屏幕自动点击）。

---

## 1. 扩展能力总览与权限分级

为了兼顾普通用户与极客需求，设计三级渐进式系统能力注入：

```
┌─────────────────────────────────────────────────────────────┐
│ 级别 1: Termux:API (零门槛免 Root)                         │
│ 适用：普通用户。通过官方 API 访问手机传感器、剪贴板与通知。   │
├─────────────────────────────────────────────────────────────┤
│ 级别 2: Shizuku / 无线调试 (免电脑 / 免 Root 拥有 ADB 权限) │
│ 适用：进阶用户。可修改系统设置、清指定 App 缓存、自动点屏幕。│
├─────────────────────────────────────────────────────────────┤
│ 级别 3: 完整 Root (`su` / Magisk / KernelSU)                │
│ 适用：极客备用机。全盘文件读写、底层内核参数修改。          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 级别 1：Termux:API 基础系统感知工具集

用户安装 `Termux:API` APK 后，Agent 动态注册以下 Python 原生工具：

### 2.1 工具列表与实现

#### 1. 系统剪贴板交互 (`android_clipboard`)
让 Agent 能直接读取用户刚刚复制的代码片段，或把生成的修复补丁直接推送到系统剪贴板：
```python
import subprocess
import json


class TermuxClipboardTool:
    @staticmethod
    def get_clipboard() -> str:
        res = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True)
        return res.stdout

    @staticmethod
    def set_clipboard(text: str) -> None:
        subprocess.run(["termux-clipboard-set"], input=text, text=True)
```

#### 2. 系统弹窗通知 (`android_notify`)
当后台长时间运行的测试或代码重构完成时，唤醒手机通知栏提示用户：
```python
def send_android_notification(title: str, content: str, priority: str = "high") -> None:
    subprocess.run(
        [
            "termux-notification",
            "--title",
            title,
            "--content",
            content,
            "--priority",
            priority,
            "--id",
            "agent_task_finished",
        ]
    )
```

#### 3. 硬件状态感知 (`android_device_info`)
感知当前是 Wi-Fi 还是流量、电量是否充足，防止手机电量低于 20% 时进行大范围高负载计算：
```python
def get_battery_status() -> dict:
    res = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
    return json.loads(res.stdout)
```

---

## 3. 级别 2：通过 Shizuku (`rish`) 实现免 Root 系统级治理

Shizuku 可以让手机上的普通应用获得 **ADB（Android Debug Bridge）级别的特权**，而完全不需要 Root 手机。

在 Termux 中配置好 `rish` 脚本后，Agent 就能直接通过执行子进程调用 ADB 核心命令，实现真正的系统级运维：

### 3.1 手机 ROM 垃圾与 App 清理工具 (`android_clean_app_cache`)
* **实现原理**：通过 ADB 的包管理器命令强力清除流氓软件或大户（如小红书、微博、特定测试 App）的缓存与残留数据：
```python
def clear_package_data(package_name: str) -> str:
    """需要用户在 ASK 模式下显式审批"""
    cmd = ["rish", "-c", f"pm clear {package_name}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return "清理成功" if "Success" in res.stdout else f"清理失败: {res.stderr}"
```

### 3.2 深度系统设置修改工具 (`android_system_settings`)
* **实现原理**：调用 `settings put [global|system|secure]` 修改系统隐藏参数：
```python
def set_system_setting(namespace: str, key: str, value: str) -> bool:
    """
    例如:
    set_system_setting("global", "window_animation_scale", "0.5")  # 加速动画
    set_system_setting("system", "screen_off_timeout", "600000")   # 改息屏时间
    """
    cmd = ["rish", "-c", f"settings put {namespace} {key} {value}"]
    res = subprocess.run(cmd)
    return res.returncode == 0
```

### 3.3 操控手机原生屏幕与应用 (`android_screen_automator`)
* **实现原理**：通过 `input` 系列底层命令模拟真人触摸屏幕，从而能够操控手机上的原生应用（如打开手机 Chrome、点击特定坐标）：
```python
class AndroidScreenAutomator:
    @staticmethod
    def tap(x: int, y: int) -> None:
        subprocess.run(["rish", "-c", f"input tap {x} {y}"])

    @staticmethod
    def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        subprocess.run(["rish", "-c", f"input swipe {x1} {y1} {x2} {y2} {duration_ms}"])

    @staticmethod
    def type_text(text: str) -> None:
        # 空格需转义为 %s
        safe_text = text.replace(" ", "%s")
        subprocess.run(["rish", "-c", f"input text '{safe_text}'"])

    @staticmethod
    def keyevent(key_code: int) -> None:
        # 3 为 HOME 键, 4 为 BACK 键
        subprocess.run(["rish", "-c", f"input keyevent {key_code}"])
```

---

## 4. 安全防护围栏（严防 Agent 越权）

**必须强化安全策略**：
这些系统级操作具有极强的现实破坏力（如误清微信数据、乱点屏幕）。因此，在 [`policy/permissions.py`](file:///d:/opencode%20program/Agent/src/agent_workspace/policy/permissions.py) 中实施以下强制铁律：

1. **绝对禁止 YOLO 自动通过**：
   凡是带有 `rish`、`pm clear`、`settings put`、`input tap` 前缀的工具调用，即使系统处于 YOLO 模式，**也必须强行中断弹出交互式确认对话框**，向用户明确展示：
   * 要操作的应用包名；
   * 要模拟点击的具体坐标或按键；
   * 必须得到用户点选 [允许] 方可放行。
2. **敏感应用黑名单**：
   在代码层硬编码禁止对系统敏感应用（如电话、短信、相册、银行、微信）执行 `pm clear` 操作。
