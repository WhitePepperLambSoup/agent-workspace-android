# Android 第三方组件、权重与对应源代码

本项目许可为仓库根 `LICENSE` 的 Apache-2.0。第三方代码/二进制/模型保留其各自许可；可选下载不改变这些条款。分发者应同时提供本页、相应完整许可和随包对应源代码，核对最终 APK 资产，而不是只依赖本页概要。

| 组件 | 固定来源/版本 | 许可与分发材料 |
|---|---|---|
| llama.cpp / ggml CPU | `ggml-org/llama.cpp` commit `7fe450e19305b828c199d602c23a8337aaa1f03b` | MIT；`build_release.py` 从固定 SHA256 源码 archive 提取上游 LICENSE 到 APK `assets/licenses/`，并记录来源/revision/digest |
| nlohmann/json 3.12.0 | 上述 llama.cpp 的 JNI JSON 头文件，许可来自官方 `v3.12.0/LICENSE.MIT` | MIT；完整文本及固定 SHA256 保存于 `licenses/nlohmann-json-3.12.0-LICENSE.txt`，准备时校验并复制到 APK |
| sherpa-onnx 1.13.8（离线语音识别 JNI，仅 arm64） | 官方 `v1.13.8` 发布包 `sherpa-onnx-v1.13.8-android-static-link-onnxruntime.tar.bz2`（35,101,751 字节，SHA256 `7583ca385ae7d981e65468455c2ea2c9f2da383921dccfc5658d0dc19d309e6f`），由 `prepare_speech_runtime.py` 校验后取出 `libsherpa-onnx-jni.so`；Kotlin 封装在 `com/k2fsa/sherpa/onnx/` | Apache-2.0；完整文本在 `licenses/sherpa-onnx-1.13.8-LICENSE.txt`，准备时复制到 APK |
| ONNX Runtime 1.28.2 | 静态链接在上述 sherpa-onnx JNI 库中 | MIT；完整文本在 `licenses/onnxruntime-1.28.2-LICENSE.txt` |
| Silero VAD | sherpa-onnx 官方 `asr-models/silero_vad.onnx`（643,854 字节，SHA256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`），随 APK 提供 | MIT（Silero Team）；完整文本在 `licenses/silero-vad-LICENSE.txt` |
| SenseVoice Small int8 语音识别模型 | `mobile_model_catalog.py` 的 `SPEECH_CATALOG`（Hugging Face `csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17` 或 ModelScope 镜像，固定 revision 与 SHA256）；分词表随 APK 提供 | FunASR Model License 1.1（FunAudioLLM / 阿里巴巴）；模型权重为用户可选下载，不打进 APK；许可文本在 `licenses/FunASR-MODEL_LICENSE.txt` |
| Qwen3 / Qwen3.5 基础模型与 Qwen3.5 视觉组件 | `mobile_model_catalog.py` 的来源、固定 GGUF revision/文件/摘要 | Apache-2.0；用户可选下载，无权重打进 APK。Qwen3 Q8_0 来自 Qwen 官方 GGUF；Q4_K_M、Qwen3.5 Q4/Q8 及 F16 mmproj 来自 Unsloth 社区发布，不能称为 Qwen 官方 GGUF |
| Gradle Wrapper 8.11.1 | Gradle 官方 `v8.11.1` 标准脚本/JAR及发布校验文件 | Apache-2.0；脚本保留原版权，摘要清单在 `gradle/wrapper/gradle-wrapper-verification.json` |
| Chaquopy 17.0.0 | 官方 `chaquo/chaquopy/17.0.0/LICENSE.txt` | MIT，Copyright 2017–2025 Chaquo Ltd and contributors；完整文本及 SHA256 保存于 `licenses/Chaquopy-17.0.0-LICENSE.txt`，准备时校验并复制到 APK。嵌入的 CPython 和 Python 依赖仍保留各自许可 |
| AndroidX、Kotlin、WorkManager、Shizuku API | Gradle 固定依赖 | Apache-2.0；保留各组件上游 notices。可选 Shizuku 服务需要用户另行安装/授权 |
| SQLite Android 3500400 | `mil.nga:sqlite-android:3500400` | 该 Maven artifact 的 POM 声明 Public Domain，来源为 SQLite Fossil；保留上游版权/公共领域说明 |
| 移动离线 Web bundle（Markdown、KaTeX 公式、图标） | `web_companion/static/mobile-vendor.js` | 保留相邻 `mobile-vendor.LICENSE.txt`（含 unified/remark/rehype、KaTeX、lucide 等各包许可） |
| Mermaid 流程图 bundle | `web_companion/static/mobile-mermaid.js`，按需加载 | Mermaid 11（MIT），许可文本在 `mobile-vendor.LICENSE.txt`；其打包依赖的许可注释保留在 bundle 内 |
| Termux PRoot 5.1.107.95 | `prepare_android_toolchain.py` 中固定官方 .deb 和源码 ZIP | GPL-2.0-only；PRoot 作为独立进程执行，不与 Agent/llama.cpp JNI 链接；源代码/许可随 APK 提供 |
| talloc 2.4.3 | 固定 Termux .deb 与 Samba 官方源码 archive | 上游 library 为 LGPL-3.0-or-later；Termux 包声明 GPL-3.0。保留完整来源许可及包声明 |
| libandroid-shmem 0.7 | 固定 Termux 官方 .deb 和源码 archive | BSD-3-Clause；完整许可随对应源码 archive 提供 |
| 可选 Alpine 3.22.6 工具环境 | `mobile_toolchain_catalog.json` arm64/x86_64 的根文件系统与全部依赖 | 按每组件许可，不用单一“Alpine 许可”覆盖：包括 Git GPL-2.0-only、Python PSF-2.0、Node MIT、Pyright 1.1.414 MIT，以及目录中每个库/工具的来源和许可 |

llama.cpp 源码 archive 为 `https://codeload.github.com/ggml-org/llama.cpp/tar.gz/7fe450e19305b828c199d602c23a8337aaa1f03b`，SHA256 `a6861d549427f814dc591c439e08206f67ffaba0248344d421589abf18199e67`。CPU 后端、mtmd 图片运行时、界定的 JNI 入口和文本/工具/图片适配进入 APK；未包含 llama.cpp 服务器或 GPU 后端。mtmd 及其 vendored 依赖的完整对应源码位于随包固定 llama.cpp archive，保留其中许可与版权。

## PRoot 二进制、对应源码和修改

构建准备将 `libagent_proot.so`、`libagent_proot_loader.so`、`libtalloc.so` 和 `libandroid-shmem.so` 放入 Android 安装后的可执行 nativeLibraryDir。PRoot 的唯一二进制修改将 DT_NEEDED `libtalloc.so.2` 字符串改为 `libtalloc.so`，以符合 Android APK 提取 lib*.so 文件的规则；没有改变 ABI。原始/修改后摘要、大小、官方 package URL 和每 ABI 文件列表记录在 APK `assets/toolchain/launchers.json`。

以下完整、摘要固定的源码 archive 和其许可文本由 `prepare_android_toolchain.py` 复制到 APK `assets/toolchain/corresponding-source/`：

| 对应源码 | SHA256 |
|---|---|
| Termux PRoot v5.1.107.95 ZIP | `dbb50381c2f0b5c342bdf3d3467d80c21d2a4677d9dadd14159fa3b32f11b319` |
| Samba talloc 2.4.3 tar.gz | `dc46c40b9f46bb34dd97fe41f548b0e8b247b77a918576733c528e83abd854dd` |
| Termux libandroid-shmem v0.7 tar.gz | `1e5ff8459bc0a8c229dd8a94b27d119987e09ef3414331c2b5ebfff20b98e867` |
| Termux 完整 recipes、patches、构建脚本，commit `f62cfca293e44326f2b838e4daf36539f920798f` | `9b59326af012166f3cfb9e1100bdf64990361d084d0350717146f40116d0c786` |

三个 gzip 源码归档在 APK 中使用标准 `.tgz` 文件名，避免 Android 资源合并自动展开 `.gz` 并改名；压缩字节、官方下载 URL 和上表摘要保持一致。`launchers.json` 同时记录 APK 中的 `file` 路径和上游 `upstream_file` 文件名，分发时应从实际 APK 逐项验证路径、大小和 SHA256。

第四份归档为 `https://codeload.github.com/termux/termux-packages/tar.gz/f62cfca293e44326f2b838e4daf36539f920798f`，9,711,757 字节；其中 proot、libtalloc、libandroid-shmem recipe 的版本及源码摘要与本 APK 使用的制品一致。四份完整归档及提取许可随 APK 提供，manifest 记录固定 recipe commit 和原 .deb 大小/摘要。talloc 的 LGPL3 文本之外，GNU 官方完整 GPL3 文本随源码附于 `licenses/GPL-3.0.txt`，准备时校验后复制到 APK（35,149 字节，SHA256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`）；其官方来源仍为 `https://www.gnu.org/licenses/gpl-3.0.txt`。

准备脚本包含确切 .deb 版本/大小/摘要、选取的成员和修改函数，运行它可复现本 APK 的启动器打包。recipe 归档包含对应 patches 和构建脚本；底层 .deb 的编译还需要其 Termux 依赖/工具链环境，因此不声称已字节一致重建上游 .deb。生成的 `assets/toolchain/NOTICE.txt` 保留不可变源码/recipe 路径和修改说明。

## 可选下载的责任与验证范围

工具环境下载约 69,020,573 字节（aarch64）或 69,344,355 字节（x86_64），还需解压/工作空间和至少 700 MiB 可用存储。目录中每个不可变制品记录 URL、精确版本、size、SHA256、origin、source 和许可。安装器验证完整性并在设备上实际执行 shell/Git/Python/Node/Pyright，存在文件或摘要正确不能替代 Android 执行成功。

若重新分发下载后的完整 rootfs 或模型权重，应一并履行各组件的源码、notice、许可和修改告知要求；本 APK 的用户可选下载方式不自动证明其他再分发方式符合许可。模型大小/RAM门槛为估计，实际推理测量与 24 场景评测分别记录，不能将第三方模型的通用成绩当成本应用的测量。
