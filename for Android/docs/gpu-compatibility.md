# 本机模型 GPU 兼容表（GPU compatibility）

本机模型默认在 CPU 上运行。GPU 加速用 llama.cpp 的 OpenCL 后端，只对高通 Adreno 7xx/8xx 和骁龙 X 系列启用（`LocalModelGpu.MINIMUM_ADRENO`）。第一次用 GPU 前，App 会在单独的进程里编译全部 GPU 内核；编译失败或引擎在 GPU 上出错时，自动改回 CPU，并在「本机模型」页说明原因。

## 已知结果

| GPU | 常见芯片 | 现在的行为 | 依据 |
| --- | --- | --- | --- |
| Adreno 750 / 810 / 830 / 840，X1 / X2 | 骁龙 8 Gen 3、8 至尊版、X Elite | 启用 GPU | llama.cpp OpenCL 后端列出的型号；本项目还没有在这类手机上实测 |
| Adreno 7xx 其他型号（如 730、740） | 骁龙 8 Gen 1、8 Gen 2、7 系列 | 启用 GPU，先过内核检查 | 未实测 |
| Adreno 660 | 骁龙 888 | 不启用，用 CPU | 实测：驱动编译 F16 矩阵内核时报 CL_OUT_OF_HOST_MEMORY 并结束进程 |
| Adreno 6xx 其他型号 | 骁龙 865、855 等 | 不启用，用 CPU | 上游说明手机上的 A6x 驱动大多会失败 |
| Mali、Immortalis、PowerVR、Xclipse | 天玑、麒麟、Exynos、Tensor 等 | 不启用，用 CPU | 当前 OpenCL 后端只支持 Adreno |

CPU 参考速度（骁龙 888，输入处理 / 生成）：Qwen3.5 0.8B 约 65 / 19 Token/s，2B 约 28 / 11 Token/s。

## 提交你的结果

1. 在「本机模型」里下载一个模型，运行一次设备测试（推理设备选「自动」）。
2. 打开「诊断」→「GPU 兼容报告」→「生成报告」→「复制报告」。
3. 点「打开 Issues 页面」，新建一个问题，标题写手机型号，把报告粘贴进去。

报告只有手机型号、芯片、Android 版本、GPU 名称（OpenCL 和 WebGL 两处读到的）、GPU 检查结果和测速，不含账号、对话或文件。有人报告某个型号能稳定运行后，这张表会更新；没有实测证据之前，不会把 Adreno 6xx 或其他 GPU 加进启用范围。

---

**English.** The on-device model runs on the CPU by default. GPU acceleration (llama.cpp's OpenCL backend) is on only for Qualcomm Adreno 7xx/8xx and Snapdragon X GPUs, after the app compiles every GPU kernel in a separate process; any failure falls back to the CPU. Tested so far: Adreno 660 (Snapdragon 888) fails the kernel compile and uses the CPU; no Adreno 7xx/8xx phone has been tested yet. To report a phone: run the device test under On-device model, then Diagnostics → GPU compatibility report → Make the report → Copy report, and paste it into a new GitHub issue.
