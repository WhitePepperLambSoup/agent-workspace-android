#!/usr/bin/env python3
"""Android 适配层与移动 Web 伴侣自动化端到端测试套件。

执行内容:
1. 单元测试: AES-256-GCM 凭据保险箱加解密机制;
2. 单元测试: Termux:API 与 Shizuku 工具定义与宿主降级机制;
3. 动态补丁测试: 运行时 patcher 注入验证;
4. 集成测试: 启动 entrypoint.py serve-mobile 并测试全部 Web API 与静态资源路由;
5. 进程清理与环境复原。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

TOTAL_TESTS = 0
PASSED_TESTS = 0


def record_result(name: str, passed: bool, detail: str = "") -> None:
    global TOTAL_TESTS, PASSED_TESTS
    TOTAL_TESTS += 1
    if passed:
        PASSED_TESTS += 1
        print(f"  [PASS] {name} {f'({detail})' if detail else ''}")
    else:
        print(f"  [FAIL] {name} - {detail}")


def test_credentials_vault() -> None:
    print("\n--- 1. 测试 AES-256-GCM 凭据存储适配器 ---")
    from android_adapter.credentials import PosixFileCredentialStore

    with tempfile.TemporaryDirectory() as temp_dir:
        vault = PosixFileCredentialStore(root_dir=Path(temp_dir))

        # 测试存取
        vault.set_credential("openai_api_key", "sk-test-key-123456")
        retrieved = vault.get_credential("openai_api_key")
        record_result("凭据加密写入与解密读取", retrieved == "sk-test-key-123456")

        # 测试不存在的键
        missing = vault.get_credential("non_existent_key")
        record_result("查询不存在凭据返回 None", missing is None)

        # 测试列表展示
        keys = vault.list_credentials()
        record_result("列出全部凭据键名", "openai_api_key" in keys and len(keys) == 1)

        # 测试删除
        deleted = vault.delete_credential("openai_api_key")
        record_result("删除已存在凭据", deleted and vault.get_credential("openai_api_key") is None)


def test_termux_api_fallbacks() -> None:
    print("\n--- 2. 测试 Termux:API 适配器与工具定义 ---")
    from android_adapter.termux_api import (
        AndroidBatteryTool,
        AndroidClipboardTool,
        AndroidNotificationTool,
        is_termux_api_available,
    )

    avail = is_termux_api_available()
    record_result("Termux:API 可用性探测正常返回布尔值", isinstance(avail, bool))

    clip_tool = AndroidClipboardTool()
    record_result("AndroidClipboardTool 规范合法", clip_tool.spec.name == "android_clipboard")

    notify_tool = AndroidNotificationTool()
    record_result("AndroidNotificationTool 规范合法", notify_tool.spec.name == "android_notify")

    battery_tool = AndroidBatteryTool()
    record_result("AndroidBatteryTool 规范合法", battery_tool.spec.name == "android_battery")


def test_shizuku_bridge() -> None:
    print("\n--- 3. 测试 Shizuku / rish 桥接机制与特权工具 ---")
    from android_adapter.shizuku import (
        AndroidAppCleanerTool,
        AndroidScreenAutomatorTool,
        is_shizuku_available,
    )

    avail = is_shizuku_available()
    record_result("Shizuku 存活探测正常返回布尔值", isinstance(avail, bool))

    cleaner_tool = AndroidAppCleanerTool()
    record_result("AndroidAppCleanerTool 规范合法", cleaner_tool.spec.name == "android_clean_app")

    screen_tool = AndroidScreenAutomatorTool()
    record_result(
        "AndroidScreenAutomatorTool 规范合法", screen_tool.spec.name == "android_screen_action"
    )


def test_patcher_injection() -> None:
    print("\n--- 4. 测试运行时 Patcher 动态注入 ---")
    from android_adapter import credentials as posix_cred
    from android_adapter.patcher import apply_android_patches

    import agent_workspace.credentials as cred_mod
    import agent_workspace.tools.pty as pty_mod

    apply_android_patches()
    record_result("凭据模块成功热替换", cred_mod.get_credential == posix_cred.get_credential)
    record_result("PTY 终端模块成功热替换", hasattr(pty_mod, "RunTerminalTool"))


class _FakeProviderHandler(BaseHTTPRequestHandler):
    """Small OpenAI-compatible SSE provider used by the Android E2E test."""

    requests: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).requests.append(body)
        payload = (
            "".join(
                f"data: {json.dumps(event)}\n\n"
                for event in (
                    {"choices": [{"delta": {"content": "android e2e ok"}}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                )
            )
            + "data: [DONE]\n\n"
        )
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def _request(
    url: str,
    *,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, bytes]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (OSError, urllib.error.URLError):
        return 0, b""


def test_web_server_endpoints() -> None:
    print("\n--- 5. 测试移动端 Web 伴侣服务接口 (E2E) ---")
    entrypoint_script = THIS_DIR / "entrypoint.py"
    _FakeProviderHandler.requests = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        workspace = root / "workspace"
        workspace.mkdir()
        database = root / "agent-data" / "agent.db"
        token_file = root / "serve.token"
        provider = ThreadingHTTPServer(("127.0.0.1", 0), _FakeProviderHandler)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            test_port = int(port_socket.getsockname()[1])
        token = "android-e2e-token"
        env = os.environ.copy()
        env.update(
            {
                "AGENT_WORKSPACE_MODEL": "android-test-model",
                "AGENT_WORKSPACE_BASE_URL": f"http://127.0.0.1:{provider.server_port}/v1",
                "AGENT_WORKSPACE_PROTOCOL": "openai-compatible",
                "AGENT_WORKSPACE_PROVIDER": "openai-compatible",
                "AGENT_WORKSPACE_API_KEY": "",
                "AGENT_WORKSPACE_ANDROID_WORKSPACE": str(workspace),
                "AGENT_WORKSPACE_ANDROID_DATABASE": str(database),
                "AGENT_WORKSPACE_SERVE_TOKEN": token,
                "AGENT_WORKSPACE_SERVE_TOKEN_FILE": str(token_file),
                "PYTHONUNBUFFERED": "1",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, str(entrypoint_script), "serve-mobile", "--port", str(test_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            base_url = f"http://127.0.0.1:{test_port}"
            server_ready = False
            for _ in range(30):
                status, _ = _request(f"{base_url}/health", token=token)
                if status == 200:
                    server_ready = True
                    break
                time.sleep(0.25)

            record_result("Web 服务在测试端口成功启动", server_ready)
            if not server_ready:
                stdout, stderr = proc.communicate(timeout=2)
                print(f"  [!] stdout={stdout[-1000:]} stderr={stderr[-1000:]}")
                return

            status, body = _request(f"{base_url}/health", token=token)
            data = json.loads(body.decode("utf-8"))
            record_result("GET /health 返回 200", status == 200 and data.get("ok") is True)

            # Static resources are intentionally usable from a WebView through the
            # query token injected into /console, while API calls use the header.
            status, body = _request(f"{base_url}/console?token={token}", token=token)
            html = body.decode("utf-8")
            record_result(
                "GET /console 返回移动版主交互界面",
                status == 200
                and "<title>Agent Workspace</title>" in html
                and 'id="appShell"' in html,
            )

            for path, marker, name in (
                (
                    f"/static/style.css?token={token}",
                    "--bg-primary:",
                    "GET /static/style.css 正常返回样式表",
                ),
                (
                    f"/static/app.js?token={token}",
                    "AndroidBridge",
                    "GET /static/app.js 正常返回前端脚本",
                ),
            ):
                status, body = _request(f"{base_url}{path}", token=token)
                record_result(name, status == 200 and marker in body.decode("utf-8"))

            status, body = _request(f"{base_url}/manifest.json?token={token}", token=token)
            manifest = json.loads(body.decode("utf-8"))
            record_result(
                "GET /manifest.json 正常返回 PWA 配置",
                status == 200 and manifest.get("display") == "standalone",
            )

            status, body = _request(f"{base_url}/sessions", token=token)
            sessions_data = json.loads(body.decode("utf-8"))
            record_result(
                "GET /sessions 返回持久化会话列表",
                status == 200 and "sessions" in sessions_data,
            )

            status, body = _request(
                f"{base_url}/sessions",
                token=token,
                method="POST",
                payload={"title": "测试移动会话"},
            )
            new_session = json.loads(body.decode("utf-8"))
            session_id = new_session.get("id")
            record_result(
                "POST /sessions 成功创建真实会话",
                status == 201 and bool(session_id) and new_session.get("title") == "测试移动会话",
            )

            status, body = _request(
                f"{base_url}/sessions/{session_id}/run",
                token=token,
                method="POST",
                payload={"prompt": "Reply with the Android E2E marker."},
            )
            run_result = json.loads(body.decode("utf-8"))
            record_result(
                "POST /sessions/{id}/run 调用真实 provider 并返回文本",
                status == 200
                and run_result.get("session_id") == session_id
                and run_result.get("text") == "android e2e ok",
            )
            record_result(
                "fake provider 收到真实 Chat Completions 请求",
                bool(_FakeProviderHandler.requests)
                and _FakeProviderHandler.requests[-1].get("model") == "android-test-model",
            )

            status, body = _request(f"{base_url}/sessions/{session_id}/events", token=token)
            events = json.loads(body.decode("utf-8")).get("events", [])
            record_result(
                "会话事件可通过 API 读取",
                status == 200 and any(event.get("type") for event in events),
            )

            status, _ = _request(f"{base_url}/sessions", token="wrong-token")
            record_result("未授权请求被拒绝", status == 401)
            record_result(
                "服务写入测试 token 文件", token_file.read_text(encoding="utf-8") == token
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=2)
            record_result("测试服务优雅注销与子进程清理", proc.poll() is not None)


def main() -> None:
    print("=" * 65)
    print("      Agent Workspace for Android: 自动化全栈验证")
    print("=" * 65)

    test_credentials_vault()
    test_termux_api_fallbacks()
    test_shizuku_bridge()
    test_patcher_injection()
    test_web_server_endpoints()

    print("\n" + "=" * 65)
    print(
        f"  测试汇总: 共运行 {TOTAL_TESTS} 项测试, 通过: {PASSED_TESTS},"
        f" 失败: {TOTAL_TESTS - PASSED_TESTS}"
    )
    print("=" * 65)

    if PASSED_TESTS == TOTAL_TESTS:
        print(">>> 全部测试通过! Android 适配层与 Web 伴侣栈运行健全。<<<\n")
        sys.exit(0)
    else:
        print("[!] 存在失败测试，请检查日志。\n")  # noqa: RUF001
        sys.exit(1)


if __name__ == "__main__":
    main()
