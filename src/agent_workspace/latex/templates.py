# ruff: noqa: E501, RUF001 -- the starter documents are LaTeX sources, kept as written.
"""Starter documents for a new LaTeX project. The article, report, slides and blank starters follow
TeXButler's (MIT, Copyright 2026 WhitePepperLambSoup)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    id: str
    main: str
    files: dict[str, str]


_PAPER_ZH = r"""\documentclass[UTF8,a4paper,12pt]{ctexart}
\usepackage{amsmath, amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{float}
\usepackage[sort&compress]{gbt7714}
\bibliographystyle{gbt7714-numerical}
\usepackage[hidelinks]{hyperref}

\title{论文题目}
\author{作者\thanks{单位，邮箱}}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
在这里写摘要：研究的问题、方法、主要结果和结论。
\end{abstract}

\noindent\textbf{关键词：}关键词一；关键词二；关键词三

\section{引言}

说明研究背景和问题。引用文献写作 \cite{lecun2015deep}，多篇文献写作 \cite{lecun2015deep,gbt7714-2015}。

\section{方法}

公式用 equation 环境，并给出标签以便引用：
\begin{equation}
  y = f(\mathbf{x}; \theta) + \varepsilon
  \label{eq:model}
\end{equation}
式~\eqref{eq:model} 中 $\theta$ 为待估参数。

\section{结果}

表格用 booktabs 三线表：
\begin{table}[H]
  \centering
  \caption{实验结果}
  \label{tab:results}
  \begin{tabular}{lcc}
    \toprule
    方法 & 指标一 & 指标二 \\
    \midrule
    方法 A & 0.91 & 0.88 \\
    方法 B & 0.94 & 0.90 \\
    \bottomrule
  \end{tabular}
\end{table}

表~\ref{tab:results} 给出了结果。

\section{结论}

总结主要发现和后续工作。

\bibliography{refs}

\end{document}
"""

_REFS_ZH = r"""@article{lecun2015deep,
  author  = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
  title   = {Deep learning},
  journal = {Nature},
  year    = {2015},
  volume  = {521},
  number  = {7553},
  pages   = {436--444},
  doi     = {10.1038/nature14539}
}

@standard{gbt7714-2015,
  author    = {{全国信息与文献标准化技术委员会}},
  title     = {信息与文献\quad 参考文献著录规则},
  number    = {GB/T 7714—2015},
  address   = {北京},
  publisher = {中国标准出版社},
  year      = {2015},
  langid    = {chinese}
}
"""

_ARTICLE_EN = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{amsmath, amssymb}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{float}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}

\title{Title of the Paper}
\author{Author Name}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
State the problem, the approach, the main results and what they mean.
\end{abstract}

\section{Introduction}

Give the background and the question. Cite a work as \cite{lecun2015deep}
and several as \cite{lecun2015deep,knuth1984texbook}.

\section{Methods}

\begin{equation}
  y = f(\mathbf{x}; \theta) + \varepsilon
  \label{eq:model}
\end{equation}
In Equation~\eqref{eq:model}, $\theta$ are the parameters.

\section{Results}

\begin{table}[H]
  \centering
  \caption{Results}
  \label{tab:results}
  \begin{tabular}{lcc}
    \toprule
    Method & Metric A & Metric B \\
    \midrule
    Method 1 & 0.91 & 0.88 \\
    Method 2 & 0.94 & 0.90 \\
    \bottomrule
  \end{tabular}
\end{table}

Table~\ref{tab:results} lists the results.

\section{Conclusion}

Summarize the findings and the next steps.

\bibliographystyle{plainnat}
\bibliography{refs}

\end{document}
"""

_REFS_EN = r"""@article{lecun2015deep,
  author  = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey},
  title   = {Deep learning},
  journal = {Nature},
  year    = {2015},
  volume  = {521},
  number  = {7553},
  pages   = {436--444},
  doi     = {10.1038/nature14539}
}

@book{knuth1984texbook,
  author    = {Knuth, Donald E.},
  title     = {The {\TeX}book},
  publisher = {Addison-Wesley},
  address   = {Reading, MA},
  year      = {1984}
}
"""

_ARTICLE_ZH = r"""\documentclass[UTF8]{ctexart}
\usepackage{graphicx}
\usepackage{float}
\usepackage{xcolor}

\title{标题}
\author{作者}
\date{\today}

\begin{document}
\maketitle

\section{开始}

在这里编写中文 LaTeX 文档，点“编译”生成 PDF。

\end{document}
"""

_REPORT_ZH = r"""\documentclass[UTF8]{ctexrep}
\usepackage{graphicx}
\usepackage{float}
\usepackage{xcolor}

\title{报告标题}
\author{作者}
\date{\today}

\begin{document}
\maketitle
\tableofcontents

\chapter{引言}

在这里编写报告。

\chapter{正文}

\section{小节}

\chapter{结论}

\end{document}
"""

_BEAMER_ZH = r"""\documentclass[UTF8]{ctexbeamer}
\usepackage{graphicx}
\usetheme{Madrid}

\title{演示标题}
\author{作者}
\date{\today}

\begin{document}

\begin{frame}
\titlepage
\end{frame}

\begin{frame}{目录}
\tableofcontents
\end{frame}

\section{第一节}

\begin{frame}{第一页}
这是幻灯片的第一页。
\end{frame}

\end{document}
"""

_BLANK = r"""\documentclass{article}
\usepackage{graphicx}

\title{Title}
\author{Author}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}

Write the document here.

\end{document}
"""

TEMPLATES: dict[str, Template] = {
    template.id: template
    for template in (
        Template("paper-zh", "main.tex", {"main.tex": _PAPER_ZH, "refs.bib": _REFS_ZH}),
        Template("paper-en", "main.tex", {"main.tex": _ARTICLE_EN, "refs.bib": _REFS_EN}),
        Template("article-zh", "main.tex", {"main.tex": _ARTICLE_ZH}),
        Template("report-zh", "main.tex", {"main.tex": _REPORT_ZH}),
        Template("slides-zh", "main.tex", {"main.tex": _BEAMER_ZH}),
        Template("blank", "main.tex", {"main.tex": _BLANK}),
    )
}


class TemplateError(Exception):
    """``unknown_template``, ``invalid_directory`` or ``exists`` (a file would be replaced)."""


def create(root: Path, directory: str, template_id: str) -> list[str]:
    """Write a starter document into ``directory`` of the folder; never replaces a file.
    Returns the created files (folder-relative), the main document first."""
    template = TEMPLATES.get(template_id)
    if template is None:
        raise TemplateError("unknown_template")
    relative = Path(directory.replace("\\", "/").strip("/")) if directory.strip() else Path()
    if relative.is_absolute() or ".." in relative.parts or len(str(relative)) > 300:
        raise TemplateError("invalid_directory")
    base = (root / relative).resolve()
    try:
        base.relative_to(root.resolve())
    except ValueError:
        raise TemplateError("invalid_directory") from None
    targets = [base / name for name in template.files]
    if any(target.exists() for target in targets):
        raise TemplateError("exists")
    base.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name, content in template.files.items():
        target = base / name
        descriptor, temporary = tempfile.mkstemp(prefix=".template-", dir=base)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            if target.exists():
                raise TemplateError("exists")
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        created.append(target.relative_to(root.resolve()).as_posix())
    main = (base / template.main).relative_to(root.resolve()).as_posix()
    return [main, *[path for path in created if path != main]]
