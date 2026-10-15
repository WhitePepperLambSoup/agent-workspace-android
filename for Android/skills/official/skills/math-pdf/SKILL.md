---
name: math-pdf
description: 用户要做带公式的文档（试卷、练习题、讲义、解题过程、公式笔记、LaTeX 文档）并导出 PDF 时使用。手机上没有 TeX，也能直接排版。
---
# 公式文档与试卷 PDF

手机上没有 pdflatex，也不需要：create_pdf 直接排版 Markdown 或 LaTeX 里的公式。不要去找或安装 TeX。

1. 选格式：
   - 用户给的是 LaTeX 源码，或要 .tex 文件：用 LaTeX 写，create_pdf 的 format 用 latex；
   - 其他情况用 Markdown + 公式（行内 $…$，独立公式 $$…$$），format 用 markdown，写起来更简单。
2. 试卷 / 练习题：
   - 标题、考试时间、总分；题型分节（选择、填空、解答），每题标分值；
   - 选择题选项用 (A)(B)(C)(D)；
   - 用户要答案时放在最后单独一节「参考答案与解析」，或另出一份 PDF。
3. 讲义 / 解题：定义 → 定理 → 例题 → 解答步骤，每一步写清依据；编号用 1.1、1.2。
4. 写完先自己检查：公式括号配对、上下标、分数、矩阵对齐；数值答案自己算一遍。
5. 用 create_pdf 生成（存到工作区 `pdf/`），再用 read_document 打开看一遍有无乱码和缺字；用户要源码时同时用 write_file 保存 .tex 或 .md。
6. 回复给出 PDF 链接和页数。
