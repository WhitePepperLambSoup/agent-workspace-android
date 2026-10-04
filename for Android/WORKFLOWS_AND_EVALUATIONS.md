# 可审阅的工作流重放与设备测量

保存目标和声明式重放兼容存在。旧目标文档包含 `prompt` 与终端 assertions；版本 2 保存实际 action steps，由 controller 的独立 execution callback 执行，不再调用模型去猜测步骤。每个动作使用当前任务的串行锁、策略、审批、事件和取消生命周期。

## 声明式文档

以下是专用 fixture 应用的示例，不是已验证的系统设置资源 ID：

```json
{
  "schema_version": 2,
  "name": "Fixture navigation",
  "preconditions": {"package": "com.example.workflowfixture"},
  "assertions": {"text_contains": "Done"},
  "steps": [{
    "step_id": "open",
    "action": "tap",
    "selector": {"resource_id": "com.example.workflowfixture:id/open"},
    "preconditions": {"text_contains": "Home"},
    "postconditions": {"text_contains": "Done"},
    "timeout_ms": 5000,
    "max_retries": 1
  }]
}
```

`tap` 与 `type_text` 需要语义 selector：`resource_id`、精确 `text`、精确 `content_description`，可另加 `class_name` 和 `package`。保存 ref、snapshot_version 或坐标会被拒绝。目标必须唯一、可见、启用、在当前 application window 且不受保护；文本输入还要求 editable。隐藏、敏感、重名、其他窗口或被截断的树不会派发动作。审批等待后再次观察和选择新 ref。

其他 action 是 `launch_app`（`package_name`）、`back` 和 `home`。每步需要非空 `preconditions` 与 `postconditions`，断言字段为 `package`、`text_contains`、`resource_id`。最多 100 步，`timeout_ms` 为 100–5000（包含审批/执行/验证），`max_retries` 为 0–2。重试只处理明确 `executed:false` 且 code 为 `stale_snapshot` 的结果，使用新树重选并计入持久化预算。

Python 管理接口供二级菜单使用：

| 方法 | 参数/返回 |
|---|---|
| `workflows.save(payload)` | 保存合法旧目标或 schema_version 2 steps |
| `workflows.start(workflow_id, payload, controller, execute)` | payload 提供会话，返回 run_id/task；实际结果在 runs |
| `workflows.run(run_id)` / `runs()` | 持久化步骤状态、执行结果、尝试数、终端状态 |
| `workflows.resume(run_id, payload, controller, execute)` | 必须 `confirm_resume:true`，检查最后确认状态后继续 |
| `workflows.export(workflow_id)` | `agent-workspace.android-workflow`、schema_version 2、workflow envelope |
| `workflows.import_document(document)` | 有界 JSON string 或上述 envelope，产生新 workflow_id |
| `workflows.record(payload)` | reviewed:true + reviewed actions，返回 workflow/dropped_actions |

录制的每项必须 `executed:true`，有语义 selector 和前/后断言；可附 `arguments` 的原执行 action/ref/version，只有重放所需的普通文本/包名会进入步骤。`password`、`is_password`、`sensitive`、`protected` 或 redacted 文本使该动作被丢弃，未确认动作也被丢弃。接口不被动观察/归档私人界面；输入文档最大 256 KiB。

## 中断与恢复

外部动作派发前提交 `dispatching` 检查点和 `action_outcome:unknown`；取得确认后先持久化 `executed` 或 `not_executed`，然后独立观察后置状态。重启会将活跃 run 标记 interrupted；仍在 dispatching 的步骤保持 unknown。已确认步骤不会重复运行。

只有无 unknown 的 interrupted 记录允许显式恢复，并在持有 controller 锁时检查最后执行步骤的 postconditions。generic task resume 拒绝 workflow replay，避免重启后误调用模型 prompt。unknown 动作不提供自动恢复：用户检查/接管设备，旧 run 保留原结果，不把一个“看似成功”的屏幕当作已确认执行。用户取消与服务关闭分别记录；等待审批时取消仍是 not_executed，派发中取消可能是 unknown。

## 测量、导出和重复运行

`MobileEvaluations.scenarios()` 的 24 条是可执行的目标/断言目录，绝不是 24 次实测通过。`evaluations.start(...)` 通过 controller 运行任务，终端断言必须独立符合当前 app window，且至少有确认执行的 Android action event。版本/电量/空间等场景还检查可见值。缺少 action evidence、task 失败、接管或中断均不能标成 success。

`evaluations.export(limit=200)` 的 `measured_runs` 只包含 `measurement_source:controller_execution`，`reviewed_records` 保留手工提交和来源无法确认的旧记录。`measured_success_rate` 仅以已结束的测量记录为分母；空数据为 null。导出保留固定 device/app_version/model/budget_steps/retry_policy、独立 evidence/action event IDs、耗时、工具步数、provider 尝试、usage（存在时）和可计算费用；没有数据的指标不会被补成假测量。最大 500 条、4 MiB，并显示截断情况。

生成固定计划使用 `evaluations.export_plan({metadata, scenario_ids, repetitions, task_retries:0})`。metadata 五字段都必填；最多 10 次 repetition、100 个总 run，model/step budget 固定，provider attempt 上限等于 budget_steps，每 task 最多 900 秒，不自动重试整个 task。CLI 接受该 schema_version 1 计划：

```sh
python "for Android/mobile_evaluation_runner.py" \
  --endpoint http://127.0.0.1:8080 \
  --plan plan.json --session-id FIXTURE_SESSION \
  --output results.json --confirm-fixture-ready
```

配对 gateway token 通过 `AGENT_WORKSPACE_MOBILE_TOKEN` 环境变量提供，不进入计划或结果。使用专用已正常解锁的中文 UI fixture 会话，固定实际设备/OEM/API、安装版本和模型，先检查没有当前 task。运行时在手机 task UI 处理正常审批；在场景间恢复声明的 fixture 状态。runner 每次检查设备/app 版本，依次提交，结果丢失或格式无效时停止，绝不重复提交不明动作。结果包含完整计划和每次实际记录。CLI 超时会请求取消 task 并停止，保留 active run/task ID；取消响应丢失时单独标记 `cancellation_outcome:unknown`，检查设备后再决定下一次独立测量。

性能报告应另外附模型 SHA/引擎 revision、线程/context/output设置、实际 token 速度/内存/电量条件、联网状态和 OS 限制。Python fixture 测试、模拟器边界测试与实际手机推理分别说明，不能合并成一个未经测量的成功率。
