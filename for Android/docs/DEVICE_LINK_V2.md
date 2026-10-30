# 手机 ↔ 电脑互联第 2 版

本文写给电脑版的开发者：安卓端在第 1 版（电脑版仓库的 [docs/DEVICE_LINK_API.md](https://github.com/WhitePepperLambSoup/agent-workspace-desktop/blob/main/docs/DEVICE_LINK_API.md)）之上加了什么，以及电脑端要做哪些改动才能和它对上。安卓端已经按本文实现（第 6 节列出改动），电脑端已按第 7 节的清单实现，两边按第 8 节在真机上做过端到端测试。

第 1 版的内容（配对、令牌、`/sessions`、`/mobile/tasks`、`/mobile/inbox` 的 `runs` 和 `approvals`、`/mobile/approvals/{id}`）不变，旧的安卓版本照常可用。

## 1. 功能一览

| # | 功能 | 安卓端 | 电脑端要做的 | 接口 |
|---|---|---|---|---|
| A | 自动批准一切 / 完全访问的对话：警告后允许 | 交任务时提示风险，确认后带上 `accept_autonomy` | 认 `accept_autonomy`；新权限 `broad_autonomy`；`/sessions` 带 `autonomy` | 2.1 |
| B | 含隐私内容（平时只给手机模型）：警告后允许 | 发现身份证号、银行卡号时提示，可打码或照发 | 认 `on_device` + `private_accepted`；运行信息带模型位置 | 2.2 |
| C | 电脑把任务交给手机，手机同意后才做 | 收到请求后由用户决定；手机自己的引擎执行，结果回传 | 电脑 AI 的 `phone_task` 工具；任务队列；收件箱 `phone_jobs` | 2.3 |
| 1 | 手机审批；电脑任务进度和完成通知；从手机停止 | 轮询收件箱、通知、审批页、停止按钮 | 收件箱 `turns`；`POST /mobile/sessions/{id}/stop`；任务的 `activity` | 2.4 |
| 2 | 在家在外都连得上，电脑换 IP 后找回 | 记住多个地址，自动切换；按电脑编号找回 | `desktop_id`；运行信息和配对链接带全部地址 | 2.5 |
| 3 | 局域网自动发现 | 用系统的 NSD 查找，点一下填好地址 | 广播 mDNS 服务；配对二维码旁显示证书指纹短码 | 2.6 |
| 4 | 手机当电脑的相机和扫描仪，「发到电脑」 | 系统分享菜单里的「发到电脑」，页面里选文件、选照片、拍照 | `PUT /mobile/files/{id}` 收文件，放进打开的文件夹 | 2.7 |
| 5 | 电脑文件到手机 | 浏览电脑文件夹、下载；收电脑推送的文件 | 文件列表和下载接口；「发到手机」；收件箱 `transfers` | 2.8 |
| 6 | 对话接力（两个方向） | 对话菜单「在电脑上继续」；接收电脑发来的对话 | `POST /mobile/conversations`；「在手机上继续」 | 2.9 |
| 7 | 手机 AI 把子任务交给电脑 | 新工具 `ask_computer`，每次都要用户同意 | 无新接口（用 2.9 和第 1 版的任务接口） | 2.10 |
| 8 | 互发文字和链接 | 发文字、发剪贴板；收到的可一键复制或打开 | `POST /mobile/messages`；收件箱 `transfers` 的文字 | 2.11 |
| 9 | 唤醒电脑 | 发网络唤醒包，等电脑上线 | 运行信息带网卡地址（需用户开启） | 2.12 |
| 10 | 定时任务结果收件箱 | 通知、列表、标记已读 | `POST /mobile/inbox/read` | 2.13 |
| 11 | 知识库同步 | 选好要对应的知识库，按内容去重，双向补齐 | 知识库列表、文档内容的读和写 | 2.14 |
| 12 | 设备管理和活动记录 | 本机记录；查看电脑上的记录；移除时同时注销 | `GET/POST /mobile/device`；`POST /mobile/device/unpair` | 2.15 |
| 13 | 在手机上审查电脑的代码改动 | 改动列表和 diff；定格成审查快照，按行评论，交给电脑上的 AI | 电脑端已做（`code_review`，电脑版 DEVICE_LINK_API.md「Code review」） | 2.16 |

## 2. 各项细节

### 通用约定

- **版本**：`GET /mobile/runtime` 返回 `"device_link": 2`。`features` 列出电脑实现了的功能，安卓端只显示列出的部分；没列出的功能，手机上不出现对应按钮。第 2 版的功能名：
  `autonomy_ack`、`private_ack`、`phone_jobs`、`turns`、`stop`、`task_activity`、`addresses`、`mdns`、`files`、`transfers`、`messages`、`conversations`、`wake`、`inbox_read`、`knowledge`、`device`，以及后加的 `code_review`（2.16）。
- **权限**：在第 1 版 `read`、`tasks`、`approvals` 之外新增三个：
  - `broad_autonomy`：可以往「自动批准一切 / 完全访问」的对话交任务（2.1）。默认不勾，勾选时电脑要提示风险。
  - `files`：收发文件和文字、浏览打开的文件夹、对话接力里的文件（2.7、2.8、2.11）。
  - `knowledge`：读写电脑的知识库（2.14）。
- **请求体大小**：默认仍是 512 KiB；`PUT /mobile/files/{id}` 最多 100 MiB；`POST /mobile/knowledge/documents` 最多 32 MiB；`POST /mobile/conversations` 最多 1 MiB。超过返回 `413 payload_too_large`。
- **轮询**：手机在引擎运行时每 20 秒取一次 `GET /mobile/inbox`。连不上时退到 60 秒，再退到 5 分钟。另外每 10 分钟取一次 `GET /mobile/runtime`。`GET /mobile/inbox` 只读本地状态，要足够快。
- **新错误码**：`autonomy_changed`、`checksum_mismatch`、`no_workspace`、`invalid_path`、`unknown_path`、`unknown_transfer`、`unknown_job`、`job_expired`、`invalid_transition`、`not_running`。格式不变：`{"error": "<code>"}`。
- **时间**：ISO 8601，带时区。
- **标识**：`*_id` 是不超过 128 个字符的字符串；手机生成的 `request_id`、`transfer_id` 用于幂等，同一个 id 再发一次返回同样的结果。

### 运行信息（第 2 版）

```
GET /mobile/runtime
{
  "idempotent_submissions": true,
  "device_link": 2,
  "app": "agent-workspace-desktop",
  "name": "Desk",
  "desktop_id": "5b0e…",                     // 电脑连接服务第一次启动时生成，之后不变；「重置手机连接」时才换
  "scopes": ["read", "tasks", "approvals", "files"],
  "features": ["tasks", "inbox", "approvals", "autonomy_ack", "…"],
  "addresses": [                              // 本服务可达的全部地址，协议和端口与当前服务一致
    {"url": "http://192.168.1.5:8765", "kind": "lan"},
    {"url": "http://100.101.1.2:8765", "kind": "tailscale"}
  ],
  "model": {"name": "deepseek-chat", "location": "cloud"},   // location: "computer"（本机或局域网里的模型）或 "cloud"
  "workspace": {"name": "report"},           // 当前打开的文件夹名，没有打开时为 null
  "defaults": {"autonomy": "workspace"},     // 新建对话用的权限设置（2.1、2.9）
  "wake": [{"mac": "aa:bb:cc:dd:ee:ff", "broadcast": "192.168.1.255"}]   // 只在用户允许唤醒时出现（2.12）
}
```

### 2.1 自动批准一切 / 完全访问的对话：警告后允许

第 1 版对这类对话一律返回 `409 desktop_autonomy_too_broad`。第 2 版改成：用户在手机上看过风险说明并确认后可以交任务，但电脑那边要先给这台手机 `broad_autonomy` 权限。

**电脑端**

1. `GET /sessions` 的每一项加上 `"autonomy": "ask" | "workspace" | "yolo" | "full_access"`。
2. `POST /mobile/tasks` 接受可选字段 `"accept_autonomy": "yolo" | "full_access"`。目标对话是 `yolo` 或 `full_access` 时：
   - 没带 `accept_autonomy`：照旧返回 `409 desktop_autonomy_too_broad`，响应里加 `"autonomy": "<当前值>"`。
   - 带了，但这台设备没有 `broad_autonomy` 权限：`403 scope_denied`。
   - 带了，但和对话当前的值不同（发出前用户改过设置）：`409 autonomy_changed`，响应里加 `"autonomy": "<当前值>"`。
   - 带了、值相同、有权限：按对话的设置运行，操作照常自动批准。
3. 任务文档加 `"autonomy"`，即这次运行实际用的设置。
4. 电脑窗口里，这一轮标出「来自手机 · 已确认自动批准」。
5. 设置里给设备勾选 `broad_autonomy` 时，提示风险：「这台手机交来的任务会在自动批准的对话里直接执行，不再询问任何人。拿到这台手机令牌的人也能这样做。」

**安卓端**

- 对话选择框里，这类对话标出「自动批准一切」或「完全访问」。
- 点「发送到此设备」时弹出确认框：「电脑上这个对话设为『自动批准一切』：交过去的任务里，运行命令、修改和删除文件、联网等操作都会直接在电脑上执行，不会再询问任何人。拿到这台手机配对令牌的人也能这样做。确定要交给它吗？」确认后请求带上 `accept_autonomy`。
- 电脑没给 `broad_autonomy` 权限时，按钮不可用，并说明要在电脑的「手机连接」里给这台手机勾上这项权限。
- 收到 `409 autonomy_changed` 时，这条交接标为失败，说明「电脑上这个对话的设置变了，请重新确认后再交」。

### 2.2 含隐私内容：警告后允许

手机平时会把含身份证号、银行卡号的消息只交给手机上的模型回答（`on_device`）。第 1 版电脑看到 `on_device: true` 一律返回 `422 unsupported_task`。

**安卓端**

- 交接时用和聊天输入框一样的规则检查要交出去的文字，包括附带的对话。发现这类号码时提示：
  「这段内容里有身份证号或银行卡号，平时只交给手机上的模型。交给电脑后，内容会发到电脑，由电脑当前的模型（{模型名}，{在这台电脑上运行 / 云端服务}）处理。」
  三个选项：「交给电脑」「打码后交给电脑」「取消」。
- 选「交给电脑」：请求带 `"on_device": true, "private_accepted": true`。选「打码后交给电脑」：号码换成打码后的样子，请求不带这两个字段。

**电脑端**

1. `POST /mobile/tasks` 带 `on_device: true` 时：
   - 同时带 `private_accepted: true`：接受。如果配置了在本机运行的模型，最好用它回答这一轮；没有就用对话的模型。
   - 没带 `private_accepted`：照旧返回 `422 unsupported_task`。
2. 任务文档加 `"model_location": "computer" | "cloud"`，表示这一轮实际由哪里的模型回答。
3. 运行信息里的 `model.location`（见上）用来让手机在提示里写清楚内容会去哪里。
4. 电脑窗口里，这一轮标出「来自手机 · 含隐私内容」。
5. `phone_control: true` 仍然返回 `422 unsupported_task`：这类任务是「操作这台手机」，电脑做不了。电脑想让手机做事走 2.3。

### 2.3 电脑把任务交给手机（手机同意后才做）

电脑上的 AI 可以请手机做事，比如「在手机上把这个文件发到微信」「看看手机上的验证短信到了没有」。手机先问用户，用户同意后由手机自己的引擎执行。手机的保护规则照常生效：银行卡号、身份证号、验证码、卸载应用、长辈模式等仍然拦截。

**电脑端**

1. 给电脑上的 AI 加工具 `phone_task`：

   ```
   phone_task(task: str, operate_phone: bool = false, device?: str, wait_minutes: int = 15)
   ```

   - `device`：手机名称或 `device_id`。只有一台接受任务的手机时可以省略。
   - `operate_phone`：需要点屏幕、操作其他应用时为 true。
   - 只有某台配对手机报告了 `accepts_jobs: true`（2.15）时才提供这个工具。
   - 调用前按电脑自己的规则审批，因为要把内容发到手机。
   - 工具一直等到任务结束、被拒、过期，或超过 `wait_minutes`，然后返回结果或原因。
2. 任务记录：

   ```
   {"job_id", "device_id", "session_id", "title", "prompt", "operate_phone",
    "state", "created_at", "expires_at", "result", "error"}
   ```

   - `state` 取值：`waiting`、`accepted`、`running`、`succeeded`、`failed`、`rejected`、`expired`、`cancelled`。
   - `title` 是电脑上那个对话的标题，手机提示里会显示。
   - `waiting` 状态 10 分钟没人处理变成 `expired`。
   - 电脑上停止那一轮时，变成 `cancelled`。
3. `GET /mobile/inbox` 加 `phone_jobs`：发给这台设备、状态为 `waiting`、`accepted`、`running`、`cancelled` 的任务，`cancelled` 只保留 1 小时，好让手机停下。最多 20 条。
4. 手机报告状态：

   ```
   POST /mobile/phone-jobs/{job_id}          权限：read
   {"state": "accepted" | "rejected" | "running" | "succeeded" | "failed",
    "result": "…",            // succeeded 时，最多 64 KiB
    "error": "…"}             // failed 时，最多 2000 字符
   → 200 {"job": {…}}
   ```

   - 允许的状态转换：`waiting` → `accepted` 或 `rejected`；`accepted` → `running` 或 `failed`；`running` → `succeeded` 或 `failed`。
   - 其他转换：`409 invalid_transition`。
   - 已过期：`410 job_expired`。
   - 不是这台设备的任务：`404 unknown_job`。
   - 同一状态重复报告返回 200，不报错。
5. 电脑窗口里显示请求状态：「等手机同意」「手机拒绝了」「手机正在做」「手机已完成」。

**安卓端**

- 每台电脑有一项设置「电脑交来的任务」：「每次询问」（默认）、「自动接受」（提示风险）、「不接受」。选「不接受」时，手机把收到的请求直接报告为 `rejected`，并向电脑报告 `accepts_jobs: false`。
- 收到请求时发通知「{电脑名} 想在这台手机上做事」，点开后看到完整内容和请求来自电脑上的哪个对话。按钮：
  - 「拒绝」；
  - 「允许，每一步询问我」；
  - 「允许，放行这个任务的操作」：相当于控制面板的「本任务都允许」。删除文件、发消息等始终逐条询问的操作仍然逐条询问。
- 接受后，在这台电脑专用的对话「{电脑名} 交来的任务」里执行，`operate_phone` 为 true 时按控制面板任务处理。
- 依次报告 `accepted`、`running`，结束时报告 `succeeded`（结果是最后一条回复）或 `failed`。
- 看到某个任务变成 `cancelled` 时，停止手机上对应的任务。

### 2.4 手机审批，电脑任务进度和完成通知，从手机停止

**电脑端**

1. 第 1 版收件箱里的 `approvals` 不变。手机按 `request_id` 发通知，审批从收件箱里消失后撤回通知。
2. `GET /mobile/inbox` 加 `turns`：电脑上最近结束的 20 轮（窗口里的和后台的都算，但不含这台手机自己交的任务，那些手机已经知道了）：

   ```
   {"turn_id", "session_id", "title", "state": "succeeded" | "failed" | "cancelled",
    "finished_at", "summary"}          // summary：最后一条回复的前 300 个字符，失败时为原因
   ```

   只在这台设备的「通知这台手机」开关打开时返回（2.15，默认开）。
3. 新接口：

   ```
   POST /mobile/sessions/{session_id}/stop      权限：tasks
   → 200 {"stopped": true}    这个对话没有在运行：409 not_running
   ```

   效果和窗口里的「停止」按钮一样。
4. 任务文档（`GET /mobile/tasks/{id}`）在 `running` 时加 `"activity": "运行 pytest"`：当前这一步在做什么，最多 120 个字符，没有就省略。

**安卓端**

- 电脑页的「等你审批」列出待审批的操作，每条有「允许」「拒绝」。新审批发通知，点开进入这一页。
- 电脑页的「正在运行」列出 `GET /sessions` 里 `running` 为 true 的对话，每个有「停止」。
- `turns` 里第一次见到的条目发通知「{电脑名} 上的任务完成了」。刚配对时已经存在的条目只记下，不通知。
- 「待发送与接力」里正在运行的任务显示 `activity`。

### 2.5 在家在外都连得上，电脑换 IP 后找回

**电脑端**

1. 运行信息带 `desktop_id` 和 `addresses`（见上）。`addresses` 列出所有局域网和 Tailscale 地址，按局域网优先排序。
2. 配对链接加可选参数（旧手机会忽略）：

   ```
   agentworkspace://pair?v=1&name=…&url=…&code=…[&fp=sha256:…]&id=<desktop_id>&alt=<另一个地址>&alt=<…>
   ```

   - `url` 是首选地址，`alt` 可以重复，每个都要 URL 编码。
   - 二维码内容变长后仍用 M 级纠错；地址太多时只放前 3 个 `alt`。
3. `POST /pair` 的 201 响应加 `desktop_id` 和 `addresses`。

**安卓端**

- 每台电脑记住全部地址，请求时先用上次成功的地址，连不上再依次试其他地址。
- 手机只对局域网地址和本机用 HTTP。Tailscale 地址要求 HTTPS，所以电脑用 HTTP 时，Tailscale 地址在手机上显示为「需要电脑开启 HTTPS」。
- 全部地址都连不上时，用局域网发现（2.6）按 `desktop_id` 找这台电脑：
  - HTTPS：证书和配对时的一致，就自动换到新地址。
  - HTTP：问用户「在 192.168.1.8 找到 Desk，换到这个地址？」，因为没有证书可以核对。

### 2.6 局域网自动发现

**电脑端**

1. 「允许手机连接这台电脑」打开时，用 mDNS / DNS-SD 广播服务：
   - 服务类型 `_agentworkspace._tcp`，实例名为电脑名，端口为服务端口。
   - TXT 记录：`v=1`、`id=<desktop_id>`、`tls=0` 或 `1`、`fp=<64 位十六进制>`（只在 HTTPS 时有）、`pair=1`（正在显示配对码时才有）。
   - 连接服务关闭时停止广播。
2. 显示配对二维码时，在旁边显示证书指纹的前 16 位，四个一组，例如 `f6f4 0160 4264 dbd9`。

**安卓端**

- 「连接电脑」里有「查找附近的电脑」，列出发现的电脑；正在显示配对码的排在前面，标「正在等待配对」。
- 点一台电脑会填好地址；HTTPS 的电脑同时填好指纹，并显示前 16 位，提示和电脑屏幕上显示的核对一致后再输入配对码。
  mDNS 不能证明发广播的就是那台电脑，所以核对这一步不能省。扫二维码不需要这一步。

### 2.7 手机当电脑的相机和扫描仪（发到电脑）

**电脑端**

```
PUT /mobile/files/{transfer_id}?name=<文件名>&size=<字节数>&sha256=<十六进制>[&knowledge=<知识库名>]
权限：files    请求体：文件原始字节（最多 100 MiB）
→ 201 {"transfer_id", "path": "来自手机/IMG_1234.jpg", "size", "knowledge_document_id"?}
```

1. 存进当前打开的文件夹下的 `来自手机/`（文件夹名可以按界面语言），重名时加「 (2)」。没有打开的文件夹：`503 no_workspace`。
2. 校验大小和 SHA-256，不一致：`400 checksum_mismatch`，不留下文件。
3. 同一个 `transfer_id` 再发一次，返回第一次的结果，不重复保存。
4. 带 `knowledge` 时，同时加入这个名字的知识库，不存在就新建。
5. 文件名去掉路径部分和控制字符，最长 200 字符。返回的 `path` 用正斜杠，相对于打开的文件夹。
6. 电脑窗口提示「手机发来了 IMG_1234.jpg」，可以打开文件或打开所在的文件夹。

**安卓端**

- 系统分享菜单里多一个「发到电脑」：可以从相册、文件管理器、微信等任何应用分享图片和文件，分享文字时按 2.11 处理。打开后选电脑，可以写一句给电脑 AI 的要求（例如「把这几张发票整理成表格」），也可以选择「加入电脑的知识库」。
- 电脑页的「文件」区有「选文件发送」「选照片发送」「拍照发送」。
- 写了要求时，上传完再交一个任务，任务里写明文件在电脑上的路径。

### 2.8 电脑文件到手机

**电脑端**

1. 浏览当前打开的文件夹：

   ```
   GET /mobile/files?path=<相对目录，默认根目录>        权限：files
   → {"path": "src", "entries": [{"name", "kind": "dir" | "file", "size", "modified_at"}], "truncated": false}
   ```

   - 不列出敏感文件（`.env`、密钥、凭据，规则同 `is_sensitive_workspace_path`）和 `.git`。
   - 最多 500 项，超出时 `truncated` 为 true。
   - 目录不存在：`404 unknown_path`。路径跳出文件夹：`400 invalid_path`。
2. 下载：

   ```
   GET /mobile/files/content?path=<相对文件路径>        权限：files
   → 原始字节，响应头带 Content-Length 和 X-Content-SHA256
   ```

   - 最多 100 MiB，超过：`413 payload_too_large`。
   - 敏感文件：`404 unknown_path`。
3. 电脑主动推送：文件右键或对话里的文件有「发到手机」，选手机后生成一条传输，放进收件箱：

   ```
   GET /mobile/inbox → "transfers": [
     {"transfer_id", "kind": "file", "name", "size", "sha256", "created_at", "from": "<对话标题或 null>"}
   ]
   GET /mobile/transfers/{transfer_id}/content     权限：read    原始字节
   POST /mobile/transfers/{transfer_id}/done       权限：read    → 200 {"ok": true}
   ```

   - 手机收好后调用 `done`，电脑删掉这条传输。没有调用的，7 天后过期。
   - 只发给选中的那台手机。

**安卓端**

- 电脑页的「文件」区可以浏览电脑上打开的文件夹，点文件就下载到手机工作区的 `来自电脑/`，下载完可以直接打开。
- 收件箱里的传输自动下载到 `来自电脑/`，发通知「收到电脑发来的 report.pdf」，点开打开文件。

### 2.9 对话接力

**手机到电脑（在电脑上继续）**

```
POST /mobile/conversations          权限：tasks（带文件时还需要 files）
{
  "request_id": "…",
  "title": "周末出行计划",
  "messages": [{"role": "user" | "assistant", "content": "…"}],   // 最多 200 条，合计不超过 1 MiB
  "files": ["<transfer_id>", …],      // 可选：先用 2.7 上传的图片和附件
  "prompt": "…"                        // 可选：建好后马上交一个任务
}
→ 201 {"session_id", "title", "task": {…}}       // 带了 prompt 才有 task
```

电脑端要做的：

1. 在当前打开的文件夹里新建对话，权限用新对话的默认设置（运行信息里的 `defaults.autonomy`）。带了 `prompt` 时，和 `POST /mobile/tasks` 一样认 `accept_autonomy`、`on_device` + `private_accepted`，规则同 2.1、2.2。被拒绝时（例如默认设置是自动批准一切、又没带 `accept_autonomy`）什么都不新建，直接返回和 `POST /mobile/tasks` 相同的错误；手机确认后用同一个 `request_id` 再发。
2. 把 `messages` 作为之前的对话记录写进去，标明「从手机接过来」。模型看到的是正常的历史消息。
3. `files` 指向的文件已经在 `来自手机/` 里，在对话开头列出它们的路径。
4. 同一个 `request_id` 再发一次，返回同一个对话，不重复新建。
5. 没有打开的文件夹：`503 no_workspace`。

**电脑到手机（在手机上继续）**

电脑的对话菜单加「在手机上继续」，选手机后生成一条传输：

```
"transfers": [{"transfer_id", "kind": "conversation", "title", "message_count", "created_at"}]
GET /mobile/transfers/{id}/content → {"title", "messages": [{"role", "content"}]}   // 规则同上
```

**安卓端**

- 对话菜单加「在电脑上继续」：把这段对话的文字发过去，对话里的图片和附件先按 2.7 上传。可以顺手写下一句要电脑接着做什么。
- 收到电脑发来的对话：在手机上新建对话「{标题}」，把记录作为历史消息放进去，发通知，点开就是这个对话。

### 2.10 手机 AI 把子任务交给电脑

只用到 2.9 和第 1 版的任务接口，电脑端不需要新接口。

**安卓端**

- 有配对的电脑时，手机 AI 多一个工具 `ask_computer(task, computer?, conversation?)`。
- 适合需要电脑的事：在电脑的项目里跑测试、处理电脑上的大文件、用电脑上登录好的网站。
- 每次调用都要用户同意，「本任务都允许」也不覆盖它，因为每次都会把内容发到另一台设备。
- 默认在电脑上新建一个对话做这件事，也可以指定已有对话的标题。
- 手机等结果回来，最多 30 分钟，再把结果交给 AI 继续回答。

**电脑端（建议）**

窗口里把这类对话标为「来自手机 · 手机 AI 交来的子任务」。

### 2.11 互发文字和链接

**手机到电脑**

```
POST /mobile/messages       权限：files
{"request_id", "kind": "text" | "link", "text": "…"}     // 最多 64 KiB
→ 201 {"ok": true}
```

电脑端要做的：

1. 窗口提示「手机发来的文字」，有「复制」按钮；链接还有「打开」。
2. 保留最近 20 条，放在「手机发来的」列表里。
3. 建议加设置「手机发来的文字自动放进剪贴板」，默认开。

**电脑到手机**

电脑可以把选中的文字或链接「发到手机」，生成传输：

```
"transfers": [{"transfer_id", "kind": "text" | "link", "text": "…", "created_at"}]
```

`text` 直接放在收件箱里，最多 64 KiB，不用另取内容；手机处理完调用 `done`。

**安卓端**

- 电脑页有「发文字」：输入框、「粘贴剪贴板」按钮和「发送」按钮。在系统分享菜单里把文字分享到「发到电脑」也会走这里。
- 收到文字发通知，通知上有「复制」；收到链接时还有「打开」。

### 2.12 唤醒电脑

**电脑端**

1. 设置里加「允许手机唤醒这台电脑」，默认关。打开时，运行信息带 `wake`：每个局域网网卡的 MAC 地址和广播地址。
2. 提示用户：要在 BIOS 和网卡驱动里开启网络唤醒，电脑要接电源，最好用网线。

**安卓端**

- 电脑连不上、而手机记住了 `wake` 时，显示「唤醒电脑」。
- 点了以后，向广播地址和 255.255.255.255 的 9 号和 7 号端口发送唤醒包，然后每 5 秒试一次，最多 2 分钟，上线后提示。
- 只在手机和电脑在同一局域网时有效，界面上写明。

### 2.13 定时任务结果收件箱

第 1 版收件箱里的 `runs` 不变。新增标记已读：

```
POST /mobile/inbox/read      权限：read
{"run_ids": ["…"]}
→ 200 {"ok": true}
```

电脑端把这些运行记录标为已读，和在电脑上读过一样。

**安卓端**

- 新的运行结果发通知「{定时任务标题} 有结果了」。
- 电脑页的「收件箱」列出结果，点开看全文，同时标记已读。
- 结果可以「在手机上继续」：新建对话，把结果放进去。

### 2.14 知识库同步

两边的知识库结构一样（电脑的 `agent_workspace.knowledge` 由手机的移植而来），所以同步交换的是**已经提取好的段落**，不是原文件（两边建好索引后都不保留原文件）。按原文件的 SHA-256 去重。删除不同步，界面上写明。

**电脑端**

1. 列出知识库：

   ```
   GET /mobile/knowledge         权限：knowledge
   → {"bases": [{"id", "name", "documents": [{"id", "title", "sha256", "pages", "passages", "updated_at"}]}]}
   ```

   - 只列已建好索引的文档，最多 2000 篇。
   - 默认知识库的 `name` 为空字符串。
2. 读取一篇文档：

   ```
   GET /mobile/knowledge/documents/{id}       权限：knowledge
   → {"id", "title", "sha256", "origin", "origin_path", "pages",
      "passages": [{"page", "heading", "text"}]}        // 最多 32 MiB
   ```

3. 写入一篇文档：

   ```
   POST /mobile/knowledge/documents           权限：knowledge    最多 32 MiB
   {"base": "<知识库名>", "title", "sha256", "origin", "origin_path", "pages", "passages": [...]}
   → 201 {"document_id"}  或已有同样 sha256 的文档时 200 {"document_id", "duplicate": true}
   ```

   - 知识库不存在就新建。
   - 文档直接是「已就绪」，不重新提取原文件。
   - 向量（按意思检索）由电脑自己补算。
   - `origin` 记为 `phone`，在知识库页面显示「来自手机」。

**安卓端**

- 电脑页的「知识库同步」可以添加对应关系：「电脑：{知识库}」对「手机：{知识库}」。
- 「现在同步」双向补齐：对方没有的文档（按 sha256）复制过去。
- 有对应关系时，每 6 小时在后台同步一次。
- 显示上次同步的时间和数量，并说明删除不会同步。

### 2.15 设备管理和活动记录

**电脑端**

1. 这台设备的信息：

   ```
   GET /mobile/device            权限：read
   → {"device_id", "name", "scopes", "created_at", "last_seen_at",
      "accepts_jobs": false, "notify": {"turns": true},
      "activity": [{"at", "action", "detail"}]}          // 最近 100 条
   ```

   `action` 取值：`paired`、`task_sent`、`task_finished`、`approval_decided`、`turn_stopped`、`file_received`、`file_sent`、`text_received`、`text_sent`、`conversation_received`、`conversation_sent`、`job_sent`、`job_finished`、`knowledge_synced`。`detail` 是一句话，最多 200 字符。
2. 手机上报自己的设置：

   ```
   POST /mobile/device           权限：read
   {"accepts_jobs": true}
   → 200 {…与 GET 相同…}
   ```

3. 手机主动解除配对：

   ```
   POST /mobile/device/unpair    权限：read    → 200 {"ok": true}
   ```

   电脑立即注销这个令牌，效果和在电脑上移除这台手机一样。
4. 设置里的设备列表显示每台手机的最近活动；每台手机有「通知这台手机（电脑上的任务完成时）」开关，默认开，对应 `notify.turns`。

**安卓端**

- 电脑页的「设备」区显示：权限、地址、配对时间、上次连上的时间、手机这边的记录（交的任务、收发的文件、审批、接受或拒绝的请求、同步）、电脑上的记录（`activity`）。
- 移除电脑时先调用 `unpair`；电脑连不上时只在手机上删除，并提示到电脑上把这台手机也移除。

### 2.16 在手机上审查电脑的代码改动

电脑端先做好（2026-10-29），接口和错误码以电脑版仓库 DEVICE_LINK_API.md 的「Code review」一节为准：`GET /mobile/changes`、`GET /mobile/changes/diff?path=`、`GET /mobile/reviews`、`GET /mobile/reviews/{id}`、`POST /mobile/reviews`、`POST /mobile/reviews/{id}/comments`、`POST /mobile/reviews/comments/{id}/followup`。读用 `read`，定格、评论、交给 AI 用 `tasks`。和电脑窗口的「变更」页走同一套处理，两边看到同一份快照和评论。

**安卓端**（`features` 有 `code_review` 时才出现）

- 电脑页「代码改动」→ 改动列表（文件、状态、增删行数）和审查记录。点文件看未提交的 diff，只读。
- 「开始审查」把当前改动定格成快照并打开；点某一行（删除的行算旧侧，其余算新侧）写评论；评论下的「交给电脑上的 AI 去改」发起后续任务，电脑在单独的工作副本里改，结果在电脑上看。重复提交收到 `followup_already_exists` 时按已交出处理，不再发起。
- 没有 `tasks` 权限时只能查看，页面说明要在电脑上给这台手机勾「交任务」。不是 Git 仓库、没有改动、diff 被截断（3000 行）都有说明。
- 手机这边的记录加 `review_comment`、`review_followup`。

## 3. 接口一览（第 2 版新增或有改动的）

| 方法和路径 | 权限 | 说明 |
|---|---|---|
| `GET /mobile/runtime` | read | 加 `device_link: 2`、`desktop_id`、`addresses`、`model`、`workspace`、`wake` |
| `POST /pair` | — | 201 响应加 `desktop_id`、`addresses` |
| `GET /sessions` | read | 每项加 `autonomy` |
| `POST /mobile/tasks` | tasks | 新字段 `accept_autonomy`、`on_device` + `private_accepted`（2.1、2.2） |
| `GET /mobile/tasks/{id}` | read | 加 `autonomy`、`model_location`、`activity` |
| `POST /mobile/sessions/{id}/stop` | tasks | 停止这个对话正在运行的一轮 |
| `GET /mobile/inbox` | read | 加 `turns`、`transfers`、`phone_jobs` |
| `POST /mobile/inbox/read` | read | 标记定时任务结果已读 |
| `POST /mobile/phone-jobs/{id}` | read | 手机报告任务状态 |
| `PUT /mobile/files/{transfer_id}` | files | 手机上传文件 |
| `GET /mobile/files` | files | 列出打开的文件夹 |
| `GET /mobile/files/content` | files | 下载文件 |
| `GET /mobile/transfers/{id}/content` | read | 电脑推给手机的文件或对话的内容 |
| `POST /mobile/transfers/{id}/done` | read | 手机收好了 |
| `POST /mobile/messages` | files | 手机发文字 |
| `POST /mobile/conversations` | tasks | 在电脑上新建对话（接力，或给 `ask_computer` 用） |
| `GET /mobile/knowledge` | knowledge | 知识库和文档清单 |
| `GET /mobile/knowledge/documents/{id}` | knowledge | 一篇文档的段落 |
| `POST /mobile/knowledge/documents` | knowledge | 写入一篇文档 |
| `GET /mobile/device`、`POST /mobile/device` | read | 这台设备的信息、设置、活动记录 |
| `POST /mobile/device/unpair` | read | 手机主动解除配对 |
| `GET /mobile/changes`、`/mobile/changes/diff`、`/mobile/reviews`、`/mobile/reviews/{id}` | read | 代码改动、diff、审查快照（2.16） |
| `POST /mobile/reviews`、`/mobile/reviews/{id}/comments`、`/mobile/reviews/comments/{id}/followup` | tasks | 定格快照、按行评论、交给电脑上的 AI（2.16） |

## 4. 收件箱（第 2 版完整形状）

```
GET /mobile/inbox
{
  "runs":       [...],   // 第 1 版
  "approvals":  [...],   // 第 1 版（只给有 approvals 权限的设备）
  "turns":      [...],   // 2.4
  "transfers":  [...],   // 2.8、2.9、2.11：kind 为 file、conversation、text、link
  "phone_jobs": [...]    // 2.3
}
```

每个列表最多 50 条，新的在前。手机按各自的 id 记住哪些已经处理过。

## 5. 电脑端界面要做的

- 「手机连接」设置：
  - 权限多 `broad_autonomy`（带风险提示）、`files`、`knowledge` 三项。
  - 配对二维码旁显示证书指纹前 16 位。
  - 新开关：「允许手机唤醒这台电脑」、「手机发来的文字自动放进剪贴板」。
  - 每台手机有「通知这台手机」开关和最近活动；「重置手机连接」会换 `desktop_id` 并注销所有手机。
- 对话和文件：「发到手机」（文件、选中的文字和链接）、「在手机上继续」（对话）、「手机发来的」列表。
- 来自手机的每一轮都要标出来，按情况标「已确认自动批准」「含隐私内容」「手机 AI 交来的子任务」。
- 电脑 AI 的 `phone_task` 工具，以及请求在窗口里的状态。
- mDNS 广播。

## 6. 安卓端的改动（已完成）

引擎（Python，`for Android/`）：

- `mobile_link.py`（新）：
  - 后台每 20 秒读一次每台电脑的收件箱，连不上时退到 60 秒、5 分钟；每 10 分钟刷新一次运行信息。
  - 处理收件箱：审批（通知；审批消失后撤回通知）；定时任务结果和电脑上结束的任务（只通知配对后新出现的）；电脑发来的文件（存到工作区「来自电脑」，校验 SHA-256）、文字、链接、对话（导入为手机上的新对话），处理完调用 `done`，连续失败 5 次后标为失败，可重试；电脑交来的任务（按设置询问、自动接受或拒绝，接受后在「{电脑名} 交来的任务」对话里执行，依次报告状态和结果；电脑取消时停下）。
  - 用户操作：审批、停止、浏览和下载电脑文件、发文件（可附带要求，自动交任务）、发文字、在电脑上继续对话（先传图片）、在新对话里交任务、唤醒电脑、知识库同步、标记已读、查看电脑上的记录。
  - 本机活动记录（每台电脑最多 300 条）。
  - 所有地址都连不上时，用局域网发现按 `desktop_id` 找回：HTTPS 证书一致就自动换地址，HTTP 先问用户。
  - 发送、下载、同步这类耗时操作在后台进行，页面轮询进度（`GET /mobile/link/operation`），不受页面请求 30 秒的限制。
- `mobile_connections.py`：
  - 每台电脑多存 `desktop_id`、全部地址、运行信息（功能、权限、模型、打开的文件夹、新对话默认设置、能否唤醒）、上次连上的时间。
  - 请求连不上时依次试其他地址，连上的地址下次先用。
  - 配对链接读 `id`、`alt`。
  - 流式上传（`PUT`）和下载（校验大小与 `X-Content-SHA256`）。
  - 移除电脑时先 `POST /mobile/device/unpair`。
  - TLS 设置只建一次，不再每个请求都建一次。
- `mobile_delivery.py`：
  - 交接带上用户确认过的 `accept_autonomy`、`on_device` + `private_accepted`。
  - 电脑明确拒绝（4xx）时标为失败并写明原因，不再反复重发。
  - 记录电脑当前这一步（`activity`）。
  - 新对话里开始的任务也进「待发送与接力」，结果照样回来。
- `mobile_knowledge.py`：新增 `extracted()`（导出一篇文档的段落）和 `add_extracted()`（直接写入别处提取好的段落，之后补算向量）。
- `android_adapter/computer_tools.py`（新）：`ask_computer` 工具。有配对电脑时，引擎下次启动才提供。它在 `mobile_approval` 的「始终逐条询问」名单里。
- `mobile_management.py`：`/mobile/link/*` 路由。

安卓原生（Kotlin）：

- `devices/ComputerDiscovery.kt`（新）：NSD 查找 `_agentworkspace._tcp`。
- `devices/ComputerSend.kt`（新）：把要发给电脑的文件复制到应用私有目录 `files/to-computer`。
- `embedded/DeviceLinkNotices.kt`：
  - 审批、电脑交来的任务、任务完成、定时任务结果、收到文件、文字、链接、对话、电脑上线、在新地址找到电脑，各有通知。
  - 文字通知带「复制」，链接通知还带「打开」。
  - 「等你确认」的通知单独一个渠道，默认都不响铃。
- `WebUiActivity.kt`：
  - 发给电脑的选文件、选照片、拍照；
  - 分享菜单「发到电脑」（`.SendToComputer` 别名）；
  - 点通知打开对应电脑页的对应位置。
- `bridge/NativeJsBridge.kt`：`pickForComputer`、`discardComputerFiles`、`discoverComputers`、`readClipboardText`。
- 资源：分享菜单名称「发到电脑」的四种语言。日文和韩文通知文字都在 `ui_text_ja.json` 和 `ui_text_ko.json` 里。

页面（`web_companion/`）：

- 「设备连接」：
  - 电脑列表显示在线状态、待审批数和待处理请求数；
  - 新增「附近的电脑」；
  - 从发现的 HTTPS 电脑填地址时，提示核对指纹前 16 位。
- 新的电脑页，依次是：
  - 状态和「唤醒电脑」；
  - 等你审批；
  - 电脑交来的任务及其设置；
  - 交任务给电脑：可选「新对话」，自动批准一切的对话和含隐私内容的交接都有确认面板；
  - 正在运行（停止）；
  - 收件箱；
  - 发文件到电脑（含浏览电脑文件）；
  - 发文字；
  - 知识库同步；
  - 设备（权限、地址、两边的记录、移除）。
- 对话设置页的「在电脑上继续」。
- 时间线里 `ask_computer` 一步显示为「让电脑做：…」。
- 四种语言的界面文字都已补齐。

测试：第 2 节的手机端行为对着一个按本文实现的假电脑端测试；另有电脑页（确认面板、审批、请求、分享来的文件）的页面测试，以及二维码识别和「发到电脑」文件复制的单元测试。测试留在开发仓库，不随公开源码发布。

### 联调后的修正（2026-10-27）

电脑端联调报告的 5 个问题，以及补测时在真机上发现的问题，处理如下（后两项是系统行为）。电脑端不用跟着改。

| 问题 | 修正 |
|---|---|
| 有「已提交」交接的电脑移除不掉（手机上留了两台 HPServer） | `POST /mobile/connections/remove` 发现还有没结果的交接时返回 `{"ok": false, "unsettled": n}`；页面说明后让用户确认，再带 `"force": true` 移除，这些交接标为失败（「结果回来之前电脑已被移除」）。旧版本留下的这类交接，后台循环会自动结束。 |
| 通知超过安卓每个应用约 50 条的上限，新通知发不出 | 新的 `notifications/NotificationBudget.kt`：发通知前，这个应用的通知超过 40 条时先删最旧的；普通消息最多留 20 条；等你确认的（审批、请求）、常驻的和前台服务的不删。同一台电脑的「任务完成」「定时任务」「上线」「换地址」各只留最新一条。 |
| 「带要求发送」被电脑拒绝后，页面还留着已经发走的文件 | `send_files` 逐个上传，返回 `sent`、`failed`、`task`、`task_error`。页面只把发走的移出列表，分别说明没发出的文件和电脑没开始处理的原因；发送按钮在列表空了以后保持不可用。 |
| 同名电脑让 `ask_computer` 选错 | 按名称或地址匹配；有几台同名时选两分钟内连上过的那台；仍分不清时报错并列出「名称（地址）」。 |
| 新配对的电脑要等引擎重启才开始读 | 每台电脑单独一个读取任务和锁，连不上的电脑不再拖住别的；单次读取最长 180 秒；意外错误记下后按退避重试；引擎的各个后台循环出错后 10 秒自动重启。 |
| 从图片或链接配对时，表单只留地址、配对码、指纹，丢了 `id` 和 `alt` | 表单内容没被改过时，页面直接把扫到的链接发给 `pair-code`。 |
| 配对链接的第一个地址连不上时配对失败 | `pair-code` 依次试链接里的其他地址，证书指纹不符时立即停止；连上的地址作为主地址，链接里的第一个地址留作备用。 |
| 电脑交来的任务在手机上的对话和「任务已完成」通知里显示一段英文说明「[A request from the AI on the paired computer …]」 | 任务请求新增 `source_note`：这段说明作为给模型的备注，不写进对话；对话和通知只显示电脑交来的原话。 |
| 几轮任务都在手机读不到时结束（比如锁屏期间），留下的「任务完成」通知不是最后结束的那一轮 | 手机按 `finished_at` 排序后依次通知（电脑的列表按开始时间排），留下的是最后结束的一轮；所有结束的任务都在电脑页的收件箱里。 |
| 电脑移除了这台手机后，电脑页显示英文「remote host returned HTTP 401」；连续重试后变成 429 | 401 显示「电脑已经不接受这台手机了，请在这里移除它再重新配对」，429 显示「电脑暂时拒绝了这台手机，请一分钟后再试」；手动输入令牌配对时 401 显示「电脑不接受这个令牌」。 |
| 移除电脑后，它的审批和请求通知还留着，点开是一台不存在的电脑 | 移除时撤回这台电脑的审批、待处理请求、任务完成、定时任务、上线和换地址通知。 |
| 锁屏约一分钟后，中兴测试机的系统（`cpufreezer`）暂停整个应用，引擎读不到电脑，电脑的审批、请求和完成通知要等亮屏后才到（应用在前台服务里运行、手机在充电也一样） | 系统行为，应用改不了；用户在系统设置里允许后台运行后才能锁屏也收到。电脑页在这种手机上（没有豁免电池优化，且是已知会限制后台的厂商，或最近一天锁屏时被暂停过）说明这一点，并给出「允许后台运行」。亮屏后一分钟内补齐：过期的请求撤回通知，完成的任务补发通知。 |
| 系统把应用的通知收成一组时，点组里的一行只打开应用首页 | 这是系统对自动分组的处理：先点组的展开箭头，再点那条通知，就会打开电脑页的对应位置。测试按用户的操作顺序来。 |

每项修正都有单元测试（移除、部分发送、同名电脑、读取互不阻塞、意外错误后重试、移除时撤回通知、配对试备用地址、通知数量、扫码配对发送链接）。

真机联调：电脑端用真实的后台服务（不开窗口，只监听 127.0.0.1，手机经 `adb reverse` 连接，模型是脚本化的本地服务），手机用带 WebView 调试的测试包，页面经 DevTools 操作，通知经下拉栏点击；第 8 节的各项都在真机上跑过，只有两项没能在测试的网络里验证：唤醒包是否到达电脑（电脑只接了有线，手机在 Wi‑Fi 上），和局域网发现（这个网络丢弃组播）。

## 7. 电脑端要做的清单

- [x] 运行信息：`device_link: 2`、`features`、`desktop_id`、`addresses`、`model`、`workspace`、`defaults`、`wake`
- [x] 配对链接：`id`、`alt`；`POST /pair` 的响应带 `desktop_id`、`addresses`
- [x] 新权限 `broad_autonomy`、`files`、`knowledge`，以及设置界面
- [x] `/sessions` 带 `autonomy`；`POST /mobile/tasks` 认 `accept_autonomy`、`on_device` + `private_accepted`；任务文档带 `autonomy`、`model_location`、`activity`
- [x] `POST /mobile/sessions/{id}/stop`
- [x] 收件箱：`turns`、`transfers`、`phone_jobs`；`POST /mobile/inbox/read`
- [x] `phone_task` 工具和请求队列；`POST /mobile/phone-jobs/{id}`
- [x] `PUT /mobile/files/{id}`、`GET /mobile/files`、`GET /mobile/files/content`
- [x] 「发到手机」（文件、文字、链接、对话）；`GET /mobile/transfers/{id}/content`、`POST /mobile/transfers/{id}/done`
- [x] `POST /mobile/messages` 和「手机发来的」列表
- [x] `POST /mobile/conversations`
- [x] 知识库三个接口
- [x] `GET/POST /mobile/device`、`POST /mobile/device/unpair`、活动记录
- [x] mDNS 广播；配对码旁显示指纹前 16 位
- [x] 「允许手机唤醒这台电脑」
- [x] 窗口里标出来自手机的每一轮

## 8. 两边都完成后的端到端测试清单

1. 扫码配对：二维码里有 `id` 和 `alt` 时，手机记住多个地址；断开局域网地址后，手机通过 `alt` 继续连上。
2. 局域网发现：手机列出正在等待配对的电脑；HTTPS 时两边显示的指纹前 16 位一致。
3. 自动批准的对话：
   - 没有 `broad_autonomy` 权限时，手机按钮不可用；
   - 有权限时，确认后交任务，电脑直接执行；
   - 电脑改了设置后再交，提示 `autonomy_changed`。
4. 含身份证号的交接：分别测「打码后交给电脑」和「交给电脑」，电脑窗口标出「含隐私内容」。
5. 电脑交任务给手机：
   - 拒绝、每步询问、放行本任务三种情况；
   - 电脑上停止时，手机也停下；
   - 手机设为「不接受」时，电脑的工具不可用。
6. 手机审批电脑上的操作；从手机停止电脑上的一轮；电脑上的任务完成时手机收到通知（不含手机自己交的）。
7. 从相册把三张照片分享到「发到电脑」，带要求「整理成表格」：文件出现在 `来自手机/`，电脑开始做任务。
8. 浏览电脑文件夹并下载一个 PDF；电脑上「发到手机」一个文件，手机收到通知并能打开。
9. 「在电脑上继续」一个带图片的对话；电脑「在手机上继续」一个对话。
10. 手机 AI 用 `ask_computer` 让电脑跑一次测试，并把结果用在回答里。
11. 互发文字和链接：复制、打开。
12. 唤醒电脑（需要支持网络唤醒的电脑；没有就跳过并记录）。
13. 定时任务结果：手机收到通知，点开后电脑上显示已读。
14. 知识库同步两个方向，按 sha256 去重；两边都能搜到对方的文档。
15. 设备页：两边的活动记录对得上；手机移除电脑后，电脑上这台手机消失。
