# 官方技能包（Official skill pack）

官方技能和 App 在同一个仓库：**`WhitePepperLambSoup/agent-workspace-android`**，源文件在 `for Android/skills/official/`。

- 每个 App 版本都**预装**打包时的官方技能（`package_apk_assets.py` 把这个文件夹放进安装包，引擎启动时 `mobile_skills.install_bundled()` 安装：第一次启动，或 App 带来的版本比已装的新时）。用户删掉官方技能后不会被自动装回来。
- 技能也单独发布为 `skills-vX.Y.Z` 的 Release，「技能」页从这里检查和下载更新，不必等 App 更新。
- 「技能」页只提供官方技能下载；别的仓库或文件里的技能可以在「导入其他技能」里手动导入，标明「非官方 · 未经测试」。

## 结构

```
for Android/skills/
├── official/                   # 技能包本身（预装进 App，也是 Release 的内容）
│   ├── skill-pack.json
│   └── skills/<名字>/SKILL.md   # 可带同目录的参考文本文件
└── tests/                      # 每个技能的真机测试记录（不打包）
```

`skill-pack.json` 的 `version` 是技能包版本（1.0.0），Release 标签为 `skills-v1.0.0`。App 安装官方包时总是用 `agent-workspace-official` 这个 id，其他来源的包占不到这个位置；「我的技能」（`my-skills`）也只有 AI 按用户要求保存的技能才能写入。

## SKILL.md

通用的 Agent Skills 格式：

```markdown
---
name: daily-checkin
description: 用户要在多个 App 里签到、领每日奖励时使用；也用于定时任务里的每日签到。
---
# 每日签到
1. ……
```

- `name`：小写字母、数字和连字符，作为技能 id。
- `description`：最多 1024 字，写清「什么时候用」。系统提示里只有这一行，AI 靠它决定要不要用 `use_skill` 读取全文。
- 正文最多 64 KB；可以引用同一文件夹里的文本文件，AI 用 `use_skill` 的 `file` 参数读取。
- 技能只是说明，不能直接执行；AI 照着做时每一步仍按用户的确认规则执行。

## 不能影响老版本的自动更新

1.6.0 及以前的 App 读取仓库的 **latest release** 并下载其中的 APK。技能 Release 绝不能成为 latest，否则这些 App 会找不到 APK。所以：

1. 技能 Release 一律以 **pre-release** 发布，并加 `--latest=false`。GitHub 从不把 pre-release 标成 latest。
2. 2.0.0 起的 App 不再依赖 latest：自己在 Release 列表里挑最新的 `vX.Y.Z` 且带 APK 的版本（`UpdateChecker.pickAppRelease`），技能则挑最新的 `skills-v*`（`mobile_skills.official_release`）。
3. `publish_skills.py publish` 固定使用上面两个参数，发布前后都检查 latest 仍是带 APK 的 App 版本，不是就报错并提示 `gh release edit vX.Y.Z --latest`。

## 发布步骤

1. 每个技能在真机上端到端测试，记录写进 `skills/tests/`。
2. 改 `skill-pack.json` 的 `version`。
3. `python publish_skills.py build`：按 App 安装时的规则校验每个技能，生成 `dist/skills/agent-workspace-skills.skillpack.zip` 和 `catalog.json`。
4. 同步到公开仓库并推送后，`python publish_skills.py publish --notes <说明文件>`（需要 gh，每次发布前确认）。
5. 和 App 同时发布时：先发 App 的 `vX.Y.Z`（成为 latest），再发 `skills-vX.Y.Z`（pre-release）。顺序反了也不要紧，pre-release 不会成为 latest，但发布后脚本会再检查一次。

## 更新

「技能」页打开时最多每 6 小时查一次官方 Release；右上角刷新会立即检查。有新版本时显示「更新到 skills-vX.Y.Z」，用户点了才更新。用户关掉的单个技能更新后保持关闭；新版本里删掉的技能会从列表消失。

## 限制

压缩包最大 20 MB，解压后最多 64 MB、3000 个文件，单个文件最大 8 MB（更大的跳过）；一个包最多 200 个技能，最多装 64 个包；系统提示里的技能目录约 6 KB，超出的只列名字。
