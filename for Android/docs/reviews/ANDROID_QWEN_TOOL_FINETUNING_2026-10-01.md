# 安卓 Qwen3.5 0.8B 工具微调与实测

本次实际执行了语言权重 LoRA 训练、合并与 GGUF 量化，并通过安卓 JNI 调用生成。
提示优化、接口修复与权重训练是三种不同工作，以下结果分别记录。
v3 权重、量化与覆盖安装已经完成；自然文件任务仍为 0/3，普通算术也有明显回退。
v4 在范围扩大后停止；v5 数据与门槛已冻结，正式微调尚未产生合格权重。
以下保留各版本实际结果，开发评分与真机任务成功分开记录。

## 基座与训练条件

- 官方基座：`Qwen/Qwen3.5-0.8B`，revision `2fc06364715b967f1860aea9cf38778875588b17`。
- 原始权重 SHA-256：`04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696`。
- 本机 RTX 4050 Laptop 6GB，CUDA PyTorch、Transformers、PEFT；没有付费云计算。
- rank 8 语言 LoRA，5,111,808 个可训练参数；基座、视觉、MTP 权重冻结。
- 合并后核对全部 488 个 tensor；150 个语言投影变化，338 个冻结 tensor 完全相同。
- 包括 153 个视觉 tensor 和 15 个 MTP tensor。tokenizer 与基座逐字节相同。
- 独立临时工作区生成训练数据，没有个人聊天、截图、凭据、手机盲测原文或原 HTML 任务答案。

## 已完成的 v1 与 v2

| 项目 | v1 | v2 |
| --- | --- | --- |
| 训练数据文件 | 320 条 | 800 条 |
| 实际优化步数 | 96 | 48 |
| v2 实际训练样本 | — | 192 个独立样本，26 族；普通问答 45 个 |
| 学习率 | 2e-4 | 5e-5 |
| v2 开发集与最终集 | — | 各 96 条，彼此独立；最终集不用于选权重 |
| v2 训练耗时 | — | 827.49 秒 |
| v2 开发集 token loss | — | 0.33490349 → 0.11655021 |
| v2 开发集各族平均 loss | — | 1.08865064 → 0.38332625 |
| 真机自然文件任务 | 0/3 | 0/3 |
| 真机原 HTML 任务 | 失败，无 HTML 文件 | 失败，无 HTML 文件 |
| 原生红/蓝图片识别 | 2/2 | 2/2 |

v1 的首份量化文件漏了 MTP tensor，加载失败；修复后可以真实推理，但工具任务仍失败。
首份坏文件、加载失败和修复后的不同 SHA 证据均保留，不能用新的通过结果覆盖原失败。

v2 在自然请求中开始正确读取源文件，但新文件使用了错误 CAS 校验值；复制任务反复写入，
耗尽六次模型调用预算。编辑能修改状态并回读，仍丢掉末尾换行。新建目录调用了未广告的工具。
因此执行过 `read_file` 或模型说“完成”都不作为完整任务成功。

## v2 独立生成与隔离执行

使用相同 runtime 提示、贪心生成、512 输出 token 上限和同一解析器：

| 指标 | 官方基座 HF | v2 LoRA HF | v2 Q4_K_M |
| --- | ---: | ---: | ---: |
| 完成评估条数 | 96 | 96 | 96 |
| 原有严格目标匹配 | 42 | 38 | 38 |
| 协议与 schema 合法 | 93 | 90 | 93 |
| 独立整数算术最终答案 | 17/25 | 1/25 | 未按此口径独立统计 |
| 可执行阶段成功 | 23/54 | 34/54 | 见执行报告 |
| 在已有历史后的完成阶段 | 11 | 16 | 见执行报告 |

原评分对文本使用子串匹配。基座有一条过程出现正确数字、最后给出错误数字，也被原评分记为正确。
独立算术审查保留所有原始回答，并核对最终答案。严重算术退步使 v2 不能作为默认推荐。
文件、todo 和 selector 的阶段评分在隔离目录实际执行；它们仍是已有历史之后的一步续写，
不能把历史里已经完成的文件状态算作新模型从头完成了任务。
Android 训练画面是合成 fixture，不能据此宣称真实手机界面操作成功率。

证据：

- [v2 真实训练报告](../../for%20Android/training/runs/tool-lora-v2-20261001/training_report.json)
- [v2 权重完整性](../../for%20Android/training/runs/tool-lora-v2-20261001/merged-weight-verification.json)
- [基座 HF 原始生成](../../output/qwen-tool-v2-base-hf-final.json)
- [v2 HF 原始生成](../../output/qwen-tool-v2-trained-hf-final.json)
- [v2 GGUF 原始生成与超时续跑记录](../../output/qwen-v2-gguf-final-combined.json)
- [独立最终答案审查](../../output/qwen-v2-preservation-final-answer-audit.json)
- [基座真实隔离执行](../../output/qwen-v2-base-hf-replay.json)
- [v2 HF 真实隔离执行](../../output/qwen-v2-trained-hf-replay.json)
- [v2 GGUF 真实隔离执行](../../output/qwen-v2-trained-gguf-replay.json)
- [v2 真机自然任务](../../output/qwen-v2-device-natural-holdout.json)
- [v2 真机 HTML](../../output/qwen-v2-device-html.json)
- [v2 真机图片识别](../../output/qwen-v2-device-vision.json)

## v3 数据与训练范围

v3 使用全新的冻结数据：400 条训练、96 条开发、96 条最终评估，共 18 族。
有 48 条自然初始复制/编辑请求需要先读源文件；其余覆盖新文件 null CAS、已有文件观察到的
64 位 SHA、精确保留首尾换行、回读、完成，以及先选择工具再建目录。
所有菜单来自实际文件任务 profile，选择后是所选工具加常驻 selector。
普通文本和算术占训练数据 30%。

全部 592 条做隐藏标签隔离、工具 schema/menu 和临时执行回放审查；554 个历史调用、
344 个目标调用真实执行。150 条算术标签独立复算正确。跨 split 的实体、文字模板和
tokenized prompt 没有重复；初始读取动作前缀跨 split 重现是有意迁移，不能称任务图完全隔离。

训练从官方基座重新开始，采用生产运行时序列化格式，完成 100 步、每步累积 4 条，
完整消费 400 条，耗时 1716.837 秒（28.61 分钟）。每 20 步对所有 96 条开发数据选择权重，
最终选中第 60 步，继承 240 个独立样本，其中普通问答 80 个（33.33%）。
最终权重没有继承第 61–100 步才训练的样本。开发 token loss 从 0.32842927 降至
0.06888069，各族平均 loss 从 0.92391704 降至 0.20410723；对话 loss 仍有退步。
最终集不参与优化或选权重。这里的生产序列化相同，不代表完整 live SYSTEM 相同；
[独立系统提示审查](../../output/qwen-v3-live-system-parity-audit.json) 明确记录了差异。

这轮的专项范围是文件工具。没有专项训练 Android 界面操作、视觉推理、调度、网页或所有其他工具；
它们仍需要独立训练和验收。视觉参数冻结也不代表语言适配后所有图片任务都不退步。

- [冻结数据及范围](../../for%20Android/training/data-v3/FROZEN.md)
- [v3 数据独立审查](../../output/qwen-v3-independent-training-audit.json)
- [v3 采样与开发检查](../../output/qwen-v3-sampling-dev-review.json)
- [v3 真实 runtime 输入追溯](../../output/qwen-v3-running-training-provenance-review.json)
- [v3 真实训练报告](../../for%20Android/training/runs/tool-lora-v3-20261001/training_report.json)
- [v3 合并与量化独立审查](../../output/qwen-v3-export-independent-audit.json)

## v3 完整独立生成与真机结果

| 指标 | 官方基座 HF | v3 LoRA HF | 官方基座 Q4_K_M | v3 Q4_K_M |
| --- | ---: | ---: | ---: | ---: |
| 最终评估完成 | 96/96 | 96/96 | 96/96 | 96/96 |
| 原有目标匹配（文本子串口径） | 47/96 | 50/96 | 53/96 | 43/96 |
| 协议/schema 合法 | 94/96 | 96/96 | 96/96 | 96/96 |
| 实际隔离工具阶段成功 | 27/66 | 41/66 | 27/66 | 36/66 |
| 预测模型完整回读 | 0/11 | 5/11 | 0/11 | 4/11 |
| 已验证历史后的完成续写 | 5/11 | 9/11 | 5/11 | 9/11 |
| 独立整数算术最终答案 | 20/25 | 6/25 | 21/25 | 5/25 |

HF 对照使用相同输入、贪心生成、512 输出 token、BF16 和原 FP32 norm/gate 路径。
基座有两条到达输出上限，训练模型没有；评分仍保留这些失败。
训练模型 `1040` 被旧子串口径误算为正确答案 `104`，独立最终答案审查不予计分。
数学正确率从 80% 降至 24%，不能宣称日常能力已保留。
独立量化对照同样从 84% 降至 20%；有九条训练回答只复述算式并提问，没有给出结果。
普通祝福请求虽关键词全匹配，量化训练模型只有 1/5 满足一句话要求，3/5 加了多余问题。
关键词分不作为通用对话能力通过率。
四路阶段回放使用同一最终评分器，fixture error 均为零；复制与编辑的写入阶段各 6 条，
四路均为 0/6。阶段总分的改善主要来自选工具、读文件和停下，并未解决关键写入错误。
这些历史状态是评分器恢复的合成前置条件，不是模型从头完成的进展；完整自主成功率另测。

量化评估固定 4096 context，仅用于可比的短样本离线评估；手机自然任务实际使用 32768 context。
这两个数字不代表应用把用户上下文重新限制为 4096。

手机自然请求完整运行后仍为 **0/3**：复制先读正确，但将源 SHA 当作新目标的 CAS，
并遗漏末尾换行；编辑写入后也未精确保留文件，并反复选择/写入直至模型调用预算耗尽；
创建目录调用了未广告工具。每项仍保持六次模型调用、八次工具调用和 420 秒预算。
没有增加提示或放宽文件字节、事件顺序、CAS 和最终完成标准。

- [基座 HF](../../output/qwen-tool-v3-base-hf-final.json)
- [v3 HF](../../output/qwen-tool-v3-trained-hf-final.json)
- [基座量化](../../output/qwen-v3-base-gguf-final.json)
- [v3 量化](../../output/qwen-v3-trained-gguf-final.json)
- [HF 独立最终答案审查](../../output/qwen-v3-preservation-final-answer-audit.json)
- [量化独立最终答案与对话审查](../../output/qwen-v3-gguf-preservation-final-answer-audit.json)
- [基座 HF 实际阶段执行](../../output/qwen-v3-base-hf-replay-final.json)
- [v3 HF 实际阶段执行](../../output/qwen-v3-trained-hf-replay-final.json)
- [基座量化实际阶段执行](../../output/qwen-v3-base-gguf-replay-final.json)
- [v3 量化实际阶段执行](../../output/qwen-v3-trained-gguf-replay-final.json)
- [v3 真机自然请求与全部轨迹](../../output/qwen-v3-device-natural-holdout.json)
- [实际导入校验](../../output/qwen-v3-device-import.json)

v3 原生红/蓝图片识别 2/2；完整 mobile 图片导入、Agent 回答与数据库恢复同样 2/2，
没有 HTTP 调用。这是两张合成颜色图片的小型测试，不是通用视觉 Agent 成绩。
证据：[native vision](../../output/qwen-v3-device-vision.json)、
[mobile vision](../../output/qwen-v3-device-vision-agent.json)。

原 HTML 请求仍失败，没有生成文件。模型先选 `code_map` 和 `web_fetch`，随后实际拉取了
65,536 字节网页，最后一次输入增长到 22,106 token，预填充约 598 秒仍未生成首个 token，
被 720 秒任务等待上限取消。没有 HTML 可进入浏览器动画与主体识别验收。
此测试的旧 HTTP 监测只覆盖 httpx；`web_fetch` 使用 http.client/socket，因此这里只能
确认模型推理在本地，不能将整个 HTML 任务称为离线。原始报告保留并另附范围审查：
[HTML 轨迹](../../output/qwen-v3-device-html.json)、
[传输范围审查](../../output/qwen-v3-html-transport-scope-audit.json)。

v3 量化模型 541,903,296 字节，SHA-256
`18aa0364bb3c936096ecd0f2de3351b8115de6588cb7c6343594f903106c4471`。
覆盖安装主 APK SHA-256
`b9a2533c1adb0ce264e6dec27b1a39fc94fec23d88a68f0d8b3f192874d445b8`。
训练权重、量化产物与旧版模型保持独立，菜单中明确标为实验模型。

## v4 冻结数据与训练规则

v4 从官方基座重新训练，使用独立生成的 600 条训练、120 条开发和120条最终样本，
每个集合普通任务占40%。普通任务包含六组基础算术、字段提取与字符串排序；
这能检查这些指定能力，不代表开放式日常对话已经保留。
文件样本涵盖36种阶段，包括新建与覆盖复制、替换/追加/删除、目录、回读、
CAS失败和文件缺失后的恢复。训练与选择都不读取最终集。

系统提示和完整适用工具列表来自手机实际 runtime，只捕获系统与工具结构。
该次桥接状态未提供无障碍 UI 工具，因此这轮不覆盖已连接的 Android 界面工具。
冻结目录包含两份经过核验的结构源，源码导出后也可重建提示。
完整 runtime/官方模板输入及目标最长2517 token，训练长度设为2560，未截断正文或历史。

独立审核检查840个真实程序、1820次工具调用、724处关键参数跨度和完整采样顺序。
评分器的89个正例、163个反例，以及开发/最终集240条标准答案执行控制均通过。
训练 CPU 回归149项通过，无跳过；这些是数据、代码与评分器检查，均非模型能力成绩。
Root另行验证840条捕获提示逐字重建匹配、隐藏答案与参数标注不进入模型输入，
以及冻结文件与审过的候选逐字节一致。

固定参数为rank 8、alpha 16、学习率1e-5、累积4、最多两轮/300次更新。
每个已消耗的样本前缀普通任务比例至少40%。函数名、CAS、选择器、编辑差量和正文边界
使用额外分组损失；视觉与原始权重保持冻结。
基座与150/300步检查点均对全部120条开发样本自由生成，再执行预测工具并核对文件结果。
每个普通和工具类别须保留基座成绩，工具总分须提高，八个关键写入类别各须通过2/2。
没有合格候选时保留真实检查点与失败证据，拒绝合格适配器和合并模型导出。
训练及后续模型评估的实际结果另行记录。

首次基座自由生成暴露了评估脚本的停止配置缺陷：本地 checkpoint 的默认 generation
配置只有 endoftext，模型输出 im_end 后仍续写伪造的用户回合，三条都到512 token。
该次运行在任何优化器更新前停止，未产生训练检查点，不计入对照成绩。
修复显式使用 im_end/endoftext 两个结束标记，并正确识别输出上限处的结束标记。
真实 tiny GPT-2 回归复现原问题并验证修复，17项测试通过；修正后的 Qwen 基座前三条
分别正常结束于148/25/38 token。后续基座和两次开发检查均使用同一修正配置。
旧原始输出和源快照保留，目录迁移另有逐项路径及SHA核验：
[停止问题诊断](../../output/qwen-v4-eos-stop-preoptimizer-diagnosis.json)、
[旧快照迁移核验](../../for%20Android/training/runs/tool-lora-v4-20261001-eos-stop-failed-preoptimizer/relocation-attestation.json)。

用户随后明确要求覆盖日常生成文件、网络搜索与多步工具使用，文件专项 v4 运行已中止。
该次修正 EOS 的运行只生成了 72/120 条基座开发输出，优化器更新次数为 0，
没有 adapter、训练检查点或合并权重。未生成的 48 条不计入准确率；
这份部分诊断不能作为完整基座能力成绩。
[中止记录](../../for%20Android/training/runs/tool-lora-v4-20261001/run-termination.json)
与[部分输出诊断](../../output/qwen-v4-interrupted-baseline-diagnostics.json)保留原始证据。

扩大范围的 v5 独立方案覆盖六种文件格式、搜索与来源整理、现有文件修改、错误恢复，
同时保留普通问答训练；它使用新的安装版工具目录与生产手机控制器系统提示。
除了单阶段开发集，还要求模型从初始状态自主完成独立的 20 项开发工作流。
最终工作流与训练、检查点选择隔离；具体预算、长度与门槛在训练前固定。
该方案实施期间的代码和数据检查不代表模型训练完成或任务可用性通过。

- [冻结说明](../../for%20Android/training/data-v4/FROZEN.md)
- [独立数据审核](../../output/qwen-v4-independent-candidate-final-audit.json)
- [独立评分器控制](../../output/qwen-v4-scorer-independent-controls.json)
- [最新训练选择审核](../../output/qwen-v4-training-helper-independent-paired-final-audit.json)
- [Root 冻结验收](../../output/qwen-v4-root-frozen-training-acceptance.json)
- [CPU 测试](../../output/qwen-v4-complete-training-cpu.xml)

## 同时修复的应用问题

Qwen XML 参数解析现在只剥一对封装换行，保留文件正文中的首尾换行。
Python 与 Kotlin 的 Android 动作 schema 对齐，Unicode 字符上限按 code point 计算；
4096 个 emoji 在 JSON bridge 中保持 Unicode，避免转义膨胀越过 native envelope。

训练模型使用独立 ID、固定文件大小和 SHA 校验，原模型保持独立。
二级菜单支持验证后的 GGUF 导入和真实模型切换。已损坏的导入文件会显示移除按钮，
使用现有确认、运行中保护和移除接口，允许清除模型自有文件后重新导入；用户其他文件保留。
没有为本机训练文件编造网络下载地址。

| 当前已有检查 | 结果 | 证据 |
| --- | --- | --- |
| 最新相关 Python 回归 | 236 通过 | [host.xml](../../output/qwen-finetuning-latest-integrated-host.xml) |
| 训练套件 CPU 环境 | 76 通过 | [training.xml](../../output/qwen-finetuning-training-cpu-runtime.xml) |
| 完整 Web 回归 | 112 通过 | [web.xml](../../output/model-corrupt-recovery-web-final.xml) |
| v2 真机菜单/Markdown/动画/Unicode | 13 通过 | [device.log](../../output/qwen-v2-device-menu-unicode-retry.log) |
| v3 真机菜单/Markdown/动画/Unicode | 13 通过 | [device.log](../../output/qwen-v3-device-menu.log) |
| v2 二级菜单实际点击切模型并恢复设置 | 通过 | [menu.json](../../output/qwen-v2-device-menu.json) |
| v3 二级菜单实际点击切模型并恢复设置 | 通过 | [menu.json](../../output/qwen-v3-device-menu.json) |
| 损坏训练模型恢复 | Python/JS 均通过 | [recovery.json](../../output/model-corrupt-recovery-verification.json) |

v2 覆盖安装 APK SHA：`008c37cebb7ffcb5de7425028b33d1e095dfd3b618c938ae2c65237eba0e61b6`。
它不含后续损坏模型恢复修复，最终 v3 构建与安装需要另行记录。
v3 完整 before/after 检查已通过：原 4 个会话、1090 条事件、设置、私有偏好和加密凭据
保持，安装 APK、268 个 Python 资源和 9 个 Web 资源逐字节一致；
唯一有意设置变化是此前要求的扩展内存模式。证据：
[v3 状态保护](../../output/android-qwen-v3-state-preservation.json)。
后续修正模型最终安装后仍需再执行此检查和恢复临时系统设置。

目前已完成真实微调和缺陷定位，v1/v2/v3 都未通过这三项基本自然文件任务。
开发 loss 降低不能证明应用已经达到成熟安卓 Agent 水平，v3 也不满足普通能力保留。
v4 基座开发生成完成 72/120，优化步数为 0；它没有产生微调权重。
v5 使用真实工具运行提示、六种文件格式、编辑恢复和搜索/抓取，1200/200/200 条阶段数据，
普通能力占 40%；另有各 20 项从初始状态开始的开发与最终工作流。正式计划为
attention-only LoRA rank16、学习率2e-5、累积4、600步，每300步完整评估。
4096 是训练完整序列预算（实测最大4079），不是 Android 的输入/上下文限制。

首次 v5 完成基座 200 项生成后，评分器把成功执行的错误 `web_search` 当作预期
`web_fetch` 结果读取并异常退出；优化仍为 0 步。原输出完整保留，评分器最小修复后
全200回放：工具阶段67/120，普通答案38/80。两项输出截断仍计失败，不删样本。
脚本标准答案200/200、隔离CPU198项通过只证明评分与执行链路，不能作为模型成绩。
后续正式执行使用独立源快照，固定合成执行路径并审计实际模块来源，避免当前
Android 设置和摘要修复改变基座/微调比较。已失败的启动记录保持独立，不冒充训练。

目前仍无合格 v5 权重；原普通能力、工具和工作流门槛保持。达到门槛前不注册为推荐模型。
证据：[评分修复独审](../../output/qwen-v5-scorer-amendment-independent-audit.json)、
[隔离回放](../../output/qwen-v5-isolated-base-full-replay-green/report.json)、
[冻结方法修正](../../output/qwen-v5-isolated-methodology-freeze-amendment.json)。
