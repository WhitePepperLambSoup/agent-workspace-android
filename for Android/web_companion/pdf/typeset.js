// Typesets create_pdf documents (Markdown, or LaTeX without a TeX installation) into this page for
// Android to print as a PDF. Markdown and math go through the app's own renderer (mobile-vendor.js,
// KaTeX); a LaTeX document is first turned into Markdown here: sectioning, lists, tables, theorem
// and proof blocks, display math with equation numbers, \newcommand macros, footnotes, page breaks.
(function (root) {
  "use strict";

  // Markers that pass through Markdown as text and become the page's own markup afterwards.
  const PAGE_BREAK = "⁣⁣PAGEBREAK⁣⁣";
  const META = "⁣⁣META⁣⁣";
  const TOC = "⁣⁣TOC⁣⁣";
  const CENTER = "⁣⁣CENTER⁣⁣";
  const STYLE_END = "⁣/STYLE⁣";
  const style = (name) => `⁣STYLE:${name}⁣`;
  // Declarations that change the rest of a group: {\large\bfseries Title}.
  const DECLARATIONS = {
    bfseries: "bold", bf: "bold", itshape: "italic", it: "italic", em: "italic", slshape: "italic",
    ttfamily: "mono", tt: "mono", scshape: "smallcaps", sc: "smallcaps", tiny: "tiny", scriptsize: "scriptsize",
    footnotesize: "footnotesize", small: "small", normalsize: "", large: "large", Large: "Large",
    LARGE: "LARGE", huge: "huge", Huge: "Huge",
  };
  const LENGTH_MM = { mm: 1, cm: 10, in: 25.4, pt: 25.4 / 72.27, bp: 25.4 / 72 };
  const DISPLAY_ENVS = {
    equation: "", "equation*": "", displaymath: "", math: "",
    align: "aligned", "align*": "aligned", flalign: "aligned", "flalign*": "aligned",
    alignat: "alignedat", "alignat*": "alignedat", eqnarray: "aligned", "eqnarray*": "aligned",
    gather: "gathered", "gather*": "gathered", multline: "gathered", "multline*": "gathered",
  };
  const THEOREMS = {
    theorem: ["定理", "Theorem"], lemma: ["引理", "Lemma"], proposition: ["命题", "Proposition"],
    corollary: ["推论", "Corollary"], definition: ["定义", "Definition"], example: ["例", "Example"],
    remark: ["注", "Remark"], exercise: ["练习", "Exercise"], problem: ["问题", "Problem"],
  };
  // Layout and font commands: nothing to show, but their arguments are not text either.
  const DROPPED = new Set([
    "label", "index", "vspace", "hspace", "vskip", "hskip", "pagestyle", "thispagestyle", "setlength",
    "addtolength", "setcounter", "addtocounter", "linespread", "fontsize", "bibliographystyle", "nocite",
    "usepackage", "documentclass", "geometry", "hypersetup", "ctexset", "graphicspath", "setmainfont",
    "setCJKmainfont", "setsansfont", "setmonofont", "definecolor", "lstset", "renewcommand", "newcommand",
    "providecommand", "DeclareMathOperator", "newtheorem", "theoremstyle", "numberwithin", "title", "author",
    "date", "phantom", "hphantom", "vphantom", "rule", "addcontentsline", "include", "input", "color",
    "pagenumbering", "bibliography", "printbibliography", "addbibresource", "captionsetup", "urlstyle",
  ]);
  const IGNORED = new Set([
    "noindent", "indent", "centering", "raggedright", "raggedleft", "small", "large", "Large", "LARGE",
    "huge", "Huge", "normalsize", "footnotesize", "scriptsize", "tiny", "bfseries", "itshape", "slshape",
    "ttfamily", "rmfamily", "sffamily", "normalfont", "upshape", "scshape", "selectfont", "maketitle",
    "hfill", "vfill", "protect", "relax", "frontmatter", "mainmatter", "backmatter", "appendix",
    "onecolumn", "twocolumn", "sloppy", "fussy", "nolinebreak", "allowbreak", "displaystyle",
  ]);
  const SYMBOLS = {
    LaTeX: "LaTeX", TeX: "TeX", LaTeXe: "LaTeX2ε", ldots: "…", dots: "…", textellipsis: "…",
    textbackslash: "\\\\", S: "§", P: "¶", copyright: "©", textregistered: "®", texttrademark: "™",
    textendash: "–", textemdash: "—", textbullet: "•", textdegree: "°", quad: " ", qquad: "  ",
    enspace: " ", thinspace: " ", textasciitilde: "~", textasciicircum: "^", textbar: "|",
    textless: "<", textgreater: ">", textquotedblleft: "“", textquotedblright: "”", textquoteleft: "‘",
    textquoteright: "’", slash: "/", i: "ı", ss: "ß", ae: "æ", oe: "œ", o: "ø", aa: "å", AE: "Æ", OE: "Œ",
  };

  function pad(text) {
    return text.replace(/[ \t]+$/gm, "");
  }

  /** The {…} group starting at text[start] (which must be "{"): its content and the index after it. */
  function group(text, start) {
    let depth = 0;
    for (let index = start; index < text.length; index += 1) {
      const character = text[index];
      if (character === "\\") { index += 1; continue; }
      if (character === "{") depth += 1;
      else if (character === "}") {
        depth -= 1;
        if (depth === 0) return [text.slice(start + 1, index), index + 1];
      }
    }
    return [text.slice(start + 1), text.length];
  }

  /** An optional [ … ] argument at text[start]; nested braces may hold brackets. */
  function optional(text, start) {
    let index = start;
    while (text[index] === " ") index += 1;
    if (text[index] !== "[") return [null, start];
    let depth = 0;
    for (let at = index; at < text.length; at += 1) {
      const character = text[at];
      if (character === "\\") { at += 1; continue; }
      if (character === "{") depth += 1;
      else if (character === "}") depth -= 1;
      else if (character === "]" && depth === 0) return [text.slice(index + 1, at), at + 1];
    }
    return [null, start];
  }

  /** A required argument: a {group}, or a single token (\cmd or one character). */
  function argument(text, start) {
    let index = start;
    while (index < text.length && /\s/.test(text[index])) index += 1;
    if (text[index] === "{") return group(text, index);
    if (text[index] === "\\") {
      const name = /^\\([A-Za-z@]+|.)/.exec(text.slice(index));
      return [name[0], index + name[0].length];
    }
    return [text[index] || "", index + 1];
  }

  /** The body of \begin{name} … \end{name} starting after the \begin, minding nested ones. */
  function environment(text, start, name) {
    const open = `\\begin{${name}}`;
    const close = `\\end{${name}}`;
    let depth = 1;
    let index = start;
    while (index < text.length) {
      const nextOpen = text.indexOf(open, index);
      const nextClose = text.indexOf(close, index);
      if (nextClose < 0) return [text.slice(start), text.length];
      if (nextOpen >= 0 && nextOpen < nextClose) { depth += 1; index = nextOpen + open.length; continue; }
      depth -= 1;
      if (depth === 0) return [text.slice(start, nextClose), nextClose + close.length];
      index = nextClose + close.length;
    }
    return [text.slice(start), text.length];
  }

  /** Splits at a top-level separator (\item, \\, &), outside groups, environments and math. */
  function splitTopLevel(text, separator) {
    const parts = [];
    let depth = 0;
    let environments = 0;
    let inMath = false;
    let last = 0;
    for (let index = 0; index < text.length; index += 1) {
      const rest = text.slice(index);
      if (rest.startsWith("\\begin{")) { environments += 1; index += 6; continue; }
      if (rest.startsWith("\\end{")) { environments -= 1; index += 4; continue; }
      if (depth === 0 && environments === 0 && !inMath && rest.startsWith(separator) &&
          !(separator === "\\item" && /^[A-Za-z]/.test(text[index + separator.length] || ""))) {
        parts.push(text.slice(last, index));
        index += separator.length - 1;
        last = index + 1;
        continue;
      }
      const character = text[index];
      if (character === "\\") { index += 1; continue; }
      if (character === "{") depth += 1;
      else if (character === "}") depth -= 1;
      else if (character === "$") inMath = !inMath;
    }
    parts.push(text.slice(last));
    return parts;
  }

  function stripComments(text) {
    return text.split("\n").map((line) => {
      for (let index = 0; index < line.length; index += 1) {
        if (line[index] === "\\") { index += 1; continue; }
        if (line[index] === "%") return line.slice(0, index);
      }
      return line;
    }).join("\n");
  }

  /** Macros a document defines, for KaTeX (\newcommand{\R}{\mathbb{R}}) and for its own text. */
  function collectMacros(text) {
    const macros = {};
    const pattern = /\\(?:re)?newcommand\*?\s*\{?\s*(\\[A-Za-z@]+)\s*\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{/g;
    let match;
    while ((match = pattern.exec(text))) {
      const [body] = group(text, pattern.lastIndex - 1);
      macros[match[1]] = body;
    }
    const operator = /\\DeclareMathOperator\*?\s*\{\s*(\\[A-Za-z@]+)\s*\}\s*\{/g;
    while ((match = operator.exec(text))) {
      const [body] = group(text, operator.lastIndex - 1);
      macros[match[1]] = `\\operatorname{${body}}`;
    }
    const definitions = /\\def\s*(\\[A-Za-z@]+)\s*\{/g;
    while ((match = definitions.exec(text))) {
      const [body] = group(text, definitions.lastIndex - 1);
      macros[match[1]] = body;
    }
    return macros;
  }

  function firstArgument(text, command) {
    const at = text.search(new RegExp(`\\\\${command}\\s*(\\[[^\\]]*\\])?\\s*\\{`));
    if (at < 0) return null;
    return group(text, text.indexOf("{", at))[0];
  }

  function today(cjk) {
    const now = new Date();
    return cjk ? `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
      : now.toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" });
  }

  /** Math as KaTeX takes it: no \label (recorded instead), \nonumber or \notag. */
  function cleanMath(body, state) {
    return body.replace(/\\label\s*\{([^}]*)\}/g, (_, name) => { state.pendingLabels.push(name); return ""; })
      .replace(/\\(nonumber|notag)\b/g, "");
  }

  /** What the preamble asks of the page: the font size of \documentclass, geometry's margins. */
  function pageSettings(preamble) {
    const settings = {};
    const options = /\\documentclass\s*\[([^\]]*)\]/.exec(preamble);
    const size = options && /(?:^|,)\s*(1[0-2])pt\s*(?:,|$)/.exec(options[1]);
    if (size) settings.fontPt = Number(size[1]);
    if (/\\pagestyle\s*\{\s*empty\s*\}/.test(preamble)) settings.pageNumbers = false;
    const geometry = [];
    for (const match of preamble.matchAll(/\\usepackage\s*\[([^\]]*)\]\s*\{geometry\}|\\geometry\s*\{([^}]*)\}/g)) {
      geometry.push(match[1] || match[2]);
    }
    const margins = {};
    for (const option of geometry.join(",").split(",")) {
      const match = /^\s*(margin|top|bottom|left|right|inner|outer|hmargin|vmargin)\s*=\s*([\d.]+)\s*(mm|cm|in|pt|bp)\s*$/.exec(option);
      if (!match) continue;
      const millimetres = Math.min(60, Number(match[2]) * LENGTH_MM[match[3]]);
      const sides = { margin: ["top", "right", "bottom", "left"], hmargin: ["left", "right"], vmargin: ["top", "bottom"],
        inner: ["left"], outer: ["right"] }[match[1]] || [match[1]];
      for (const side of sides) margins[side] = millimetres;
    }
    if (Object.keys(margins).length) settings.margins = margins;
    return settings;
  }

  /** A LaTeX document as Markdown, with the macros KaTeX needs. */
  function latexToMarkdown(source) {
    let text = stripComments(String(source || "").replace(/\r\n?/g, "\n"));
    const macros = collectMacros(text);
    const cjk = /[㐀-鿿]/.test(text) || /\\usepackage(\[[^\]]*\])?\{ctex\}|\\documentclass(\[[^\]]*\])?\{ctex/.test(text);
    const begin = text.indexOf("\\begin{document}");
    const preamble = begin >= 0 ? text.slice(0, begin) : "";
    let body = begin >= 0 ? text.slice(begin + "\\begin{document}".length) : text;
    const end = body.indexOf("\\end{document}");
    if (end >= 0) body = body.slice(0, end);
    const theorems = {};
    for (const match of (preamble + body).matchAll(/\\newtheorem\*?\{([^}]+)\}(?:\[[^\]]*\])?\{([^}]+)\}/g)) {
      theorems[match[1]] = match[2];
    }
    const state = {
      cjk, macros, theorems, footnotes: [], headings: [], counters: { chapter: 0, section: 0, subsection: 0, subsubsection: 0 },
      hasChapters: /\\chapter\b/.test(body), equation: 0, figure: 0, table: 0, theorem: {}, labels: {}, pendingLabels: [],
      float: null,
      title: firstArgument(preamble + body, "title"), author: firstArgument(preamble + body, "author"),
      date: firstArgument(preamble + body, "date"),
    };
    // Source indentation is not code: Markdown would read four leading spaces as a code block.
    body = body.replace(/\n[ \t]+/g, "\n");
    let markdown = convert(body, state);
    if (state.footnotes.length) {
      markdown += "\n\n" + state.footnotes.map((note, index) => `[^${index + 1}]: ${note.replace(/\n+/g, " ")}`).join("\n");
    }
    markdown = markdown.replace(/⁣⁣REF\{([^}]*)\}⁣⁣/g, (_, name) => state.labels[name] || "??");
    if (markdown.includes(TOC)) {
      const contents = state.headings.map(({ level, title }) => `${"  ".repeat(level)}- ${title}`).join("\n");
      markdown = markdown.replace(TOC, `\n\n**${cjk ? "目录" : "Contents"}**\n\n${contents}\n\n`);
    }
    return { markdown: pad(markdown).replace(/\n{3,}/g, "\n\n").trim(), macros, cjk, page: pageSettings(preamble) };
  }

  /** {\large\bfseries text}: the declarations at the start of a group, and the rest of it. */
  function declarations(text) {
    const styles = [];
    let rest = text;
    for (;;) {
      const match = /^\s*\\([A-Za-z]+)\b\s*/.exec(rest);
      if (!match || !(match[1] in DECLARATIONS) && match[1] !== "centering") break;
      if (match[1] !== "centering" && DECLARATIONS[match[1]]) styles.push(DECLARATIONS[match[1]]);
      rest = rest.slice(match[0].length);
    }
    return [styles, rest];
  }

  function styled(styles, content) {
    const trimmed = content.trim();
    if (!styles.length || !trimmed) return content;
    // Per paragraph, so every span closes inside the paragraph it opened in.
    return trimmed.split(/\n{2,}/).map((paragraph) =>
      styles.map(style).join("") + paragraph + STYLE_END.repeat(styles.length)).join("\n\n");
  }

  function heading(name, star, title, state) {
    const levels = state.hasChapters ? { chapter: 2, section: 3, subsection: 4, subsubsection: 5 }
      : { chapter: 2, section: 2, subsection: 3, subsubsection: 4 };
    const level = name === "part" ? 2 : levels[name] || 5;
    let number = "";
    if (!star && name in state.counters) {
      const order = ["chapter", "section", "subsection", "subsubsection"];
      const position = order.indexOf(name);
      state.counters[name] += 1;
      for (const deeper of order.slice(position + 1)) state.counters[deeper] = 0;
      const parts = order.slice(state.hasChapters ? 0 : 1, position + 1).map((key) => state.counters[key]);
      number = name === "chapter" ? (state.cjk ? `第 ${parts[0]} 章` : `Chapter ${parts[0]}`) : parts.join(".");
      state.lastNumber = parts.join(".");
    }
    const shown = number ? `${number} ${title}` : title;
    state.headings.push({ level: Math.max(0, level - 2), title: shown });
    return `\n\n${"#".repeat(level)} ${shown}\n\n`;
  }

  function list(name, content, state) {
    const items = splitTopLevel(content, "\\item").slice(1);
    return "\n\n" + items.map((item, index) => {
      let [label, rest] = optional(item, 0);
      const converted = convert(item.slice(rest), state).trim().replace(/\n{2,}/g, "\n\n");
      let marker = name === "enumerate" ? `${index + 1}.` : "-";
      let lead = "";
      if (label !== null) {
        if (name === "description") lead = `**${convert(label, state).trim()}** `;
        else { marker = "-"; lead = `${convert(label, state).trim()} `; }
      }
      const indent = " ".repeat(marker.length + 1);
      return `${marker} ${lead}${converted.split("\n").map((line, at) => (at && line ? indent + line : line)).join("\n")}`;
    }).join("\n") + "\n\n";
  }

  function table(content, spec, state) {
    const aligns = [];
    for (const match of (spec || "").replace(/@\{[^}]*\}|>\{[^}]*\}|<\{[^}]*\}|\|/g, "").matchAll(/([lcrX])|[pmb]\{[^}]*\}/g)) {
      aligns.push(match[1] === "c" ? ":-:" : match[1] === "r" ? "--:" : match[1] === "l" ? ":--" : "---");
    }
    const rows = splitTopLevel(content.replace(/\\(hline|toprule|midrule|bottomrule|endhead|endfirsthead|endfoot|endlastfoot)\b/g, "")
      .replace(/\\(cline|cmidrule)(\([^)]*\))?\{[^}]*\}/g, ""), "\\\\")
      // A row's extra space (\\[2pt]) is not part of the next row.
      .map((row) => row.trim().replace(/^\[[^\]]*\]\s*/, "")).filter(Boolean)
      .map((row) => splitTopLevel(row, "&").flatMap((cell) => {
        const at = cell.search(/^\s*\\multicolumn\b/) === 0 ? cell.indexOf("\\multicolumn") + "\\multicolumn".length : -1;
        if (at >= 0) {
          const [count, afterCount] = argument(cell, at);
          const [, afterSpec] = argument(cell, afterCount);
          const [inner] = argument(cell, afterSpec);
          return [inner, ...Array(Math.max(0, (Number(count) || 1) - 1)).fill("")];
        }
        return [cell];
      }).map((cell) => convert(cell, state).replace(/\s*\n\s*/g, " ").replace(/\|/g, "\\|").trim() || " "));
    if (!rows.length) return "";
    const width = Math.max(...rows.map((row) => row.length));
    const line = (cells) => `| ${[...cells, ...Array(width - cells.length).fill(" ")].join(" | ")} |`;
    const rule = `| ${Array.from({ length: width }, (_, index) => aligns[index] || "---").join(" | ")} |`;
    return `\n\n${line(rows[0])}\n${rule}\n${rows.slice(1).map(line).join("\n")}\n\n`;
  }

  function displayMath(name, body, state) {
    const wrapper = DISPLAY_ENVS[name];
    let math = cleanMath(body, state).trim();
    if (wrapper) {
      const columns = wrapper === "alignedat" ? /^\s*\{(\d+)\}/.exec(math) : null;
      if (columns) math = math.slice(columns[0].length);
      math = `\\begin{${wrapper}}${columns ? `{${columns[1]}}` : ""}${math}\\end{${wrapper}}`;
    }
    if (!name.endsWith("*") && name !== "displaymath" && name !== "math") {
      state.equation += 1;
      math += `\\tag{${state.equation}}`;
      for (const label of state.pendingLabels) state.labels[label] = String(state.equation);
    }
    state.pendingLabels = [];
    return `\n\n$$\n${math}\n$$\n\n`;
  }

  function environmentBlock(name, body, state) {
    if (name in DISPLAY_ENVS) return displayMath(name, body, state);
    if (name === "itemize" || name === "enumerate" || name === "description") return list(name, body, state);
    if (["tabular", "tabular*", "tabularx", "longtable", "array", "tabulary"].includes(name)) {
      let rest = body;
      if (name === "tabular*" || name === "tabularx" || name === "tabulary") rest = argument(rest, 0)[1] ? rest.slice(argument(rest, 0)[1]) : rest;
      const [spec, after] = argument(rest, optional(rest, 0)[1]);
      return table(rest.slice(after), spec, state);
    }
    if (["verbatim", "verbatim*", "lstlisting", "minted", "Verbatim", "code"].includes(name)) {
      let code = body;
      let language = "";
      if (name === "minted") { const [lang, after] = argument(code, optional(code, 0)[1]); language = lang; code = code.slice(after); }
      else if (name === "lstlisting") {
        const [options, after] = optional(code, 0);
        const match = options && /language\s*=\s*([\w+#-]+)/.exec(options);
        language = match ? match[1].toLowerCase() : "";
        code = code.slice(after);
      }
      return `\n\n\`\`\`${language}\n${code.replace(/^\n+|\s+$/g, "")}\n\`\`\`\n\n`;
    }
    if (["quote", "quotation", "verse"].includes(name)) {
      return "\n\n" + convert(body, state).trim().split("\n").map((line) => `> ${line}`).join("\n") + "\n\n";
    }
    if (name === "abstract") {
      return `\n\n**${state.cjk ? "摘要" : "Abstract"}** ${convert(body, state).trim()}\n\n`;
    }
    if (name === "proof") {
      const [label, after] = optional(body, 0);
      const title = label !== null ? convert(label, state).trim() : (state.cjk ? "证明" : "Proof");
      return `\n\n*${title}.* ${convert(body.slice(after), state).trim()} ∎\n\n`;
    }
    const theorem = state.theorems[name] || (THEOREMS[name.replace(/\*$/, "")] || [])[state.cjk ? 0 : 1];
    if (theorem) {
      const [note, after] = optional(body, 0);
      let label = theorem;
      if (!name.endsWith("*")) {
        state.theorem[name] = (state.theorem[name] || 0) + 1;
        label += ` ${state.theorem[name]}`;
      }
      const remark = note !== null ? `（${convert(note, state).trim()}）` : "";
      return `\n\n**${label}${remark}.** ${convert(body.slice(after), state).trim()}\n\n`;
    }
    if (name === "figure" || name === "figure*" || name === "table" || name === "table*") {
      // Captions and labels anywhere inside (a center block, a minipage) belong to this float.
      const outer = state.float;
      state.float = name.startsWith("figure") ? "figure" : "table";
      const inner = convert(body.slice(optional(body, 0)[1]), state);
      state.float = outer;
      return `\n\n${inner.trim()}\n\n`;
    }
    if (name === "thebibliography") {
      const items = splitTopLevel(body.slice(argument(body, 0)[1]), "\\bibitem").slice(1);
      return `\n\n## ${state.cjk ? "参考文献" : "References"}\n\n` + items.map((item, index) => {
        const [, afterLabel] = optional(item, 0);
        const [, afterKey] = argument(item, afterLabel);
        return `${index + 1}. ${convert(item.slice(afterKey), state).trim()}`;
      }).join("\n") + "\n\n";
    }
    if (name === "center") {
      // Centred paragraphs (a hand-made title block); formulas and tables are centred anyway.
      const [styles, rest] = declarations(body);
      return "\n\n" + convert(rest, state).trim().split(/\n{2,}/).map((paragraph) =>
        /^(\$\$|\||#|- |\d+\. |```|>)/.test(paragraph) ? paragraph : CENTER + styled(styles, paragraph)).join("\n\n") + "\n\n";
    }
    if (name === "flushleft" || name === "flushright" || name === "minipage" || name === "document") {
      const rest = name === "minipage" ? body.slice(argument(body, optional(body, 0)[1])[1]) : body;
      return `\n\n${convert(rest, state).trim()}\n\n`;
    }
    return convert(body, state);
  }

  /** Text mode: commands, environments and math to Markdown. */
  function convert(text, state) {
    const float = state.float;
    let out = "";
    let index = 0;
    while (index < text.length) {
      const character = text[index];
      if (character === "\\") {
        const next = text[index + 1];
        if (next === undefined) break;
        if ("%&#_{}$".includes(next)) { out += next === "_" || next === "#" || next === "$" ? `\\${next}` : next; index += 2; continue; }
        if (next === "\\") {
          index = optional(text, index + 2)[1];
          out += "  \n";
          continue;
        }
        if (next === "[" || next === "(") {
          const close = next === "[" ? "\\]" : "\\)";
          const end = text.indexOf(close, index + 2);
          const body = cleanMath(text.slice(index + 2, end < 0 ? text.length : end), state);
          state.pendingLabels = [];
          out += next === "[" ? `\n\n$$\n${body.trim()}\n$$\n\n` : `$${body.trim()}$`;
          index = end < 0 ? text.length : end + 2;
          continue;
        }
        if (" ,;:!".includes(next)) { out += next === " " ? " " : " "; index += 2; continue; }
        // Discretionary hyphen, italic correction, end of sentence: nothing to show.
        if ("-/@".includes(next)) { index += 2; continue; }
        if ("'`^\"~=.uvHcdbtr".includes(next) && !/[A-Za-z]/.test(text[index + 2] || "") || "'`^\"~=.".includes(next)) {
          // An accent: keep the letter (the accented form is rare in documents written here).
          const [letter, after] = argument(text, index + 2);
          out += convert(letter, state);
          index = after;
          continue;
        }
        const match = /^[A-Za-z@]+\*?/.exec(text.slice(index + 1));
        if (!match) { out += next; index += 2; continue; }
        const name = match[0];
        index += 1 + name.length;
        const plain = name.replace(/\*$/, "");
        const star = name.endsWith("*");
        if (plain === "begin") {
          const [environmentName, after] = argument(text, index);
          const [body, end] = environment(text, after, environmentName);
          out += environmentBlock(environmentName, body, state);
          index = end;
          continue;
        }
        if (plain === "end") { index = argument(text, index)[1]; continue; }
        if (["part", "chapter", "section", "subsection", "subsubsection"].includes(plain)) {
          const [, afterShort] = optional(text, index);
          const [title, after] = argument(text, afterShort);
          out += heading(plain, star, convert(title, state).trim(), state);
          index = after;
          continue;
        }
        if (plain === "paragraph" || plain === "subparagraph") {
          const [title, after] = argument(text, optional(text, index)[1]);
          out += `\n\n**${convert(title, state).trim()}** `;
          index = after;
          continue;
        }
        if (plain === "maketitle") {
          const lines = [];
          if (state.title) lines.push(`# ${convert(state.title, state).replace(/\s*\n\s*/g, " ").trim()}`);
          if (state.author) lines.push(META + convert(state.author.replace(/\s*\\and\b\s*/g, ", "), state).replace(/\s*\n\s*/g, " ").trim());
          const date = state.date === null ? today(state.cjk) : state.date.trim() && convert(state.date, state).trim();
          if (date) lines.push(META + date);
          out += `\n\n${lines.join("\n\n")}\n\n`;
          continue;
        }
        if (plain === "tableofcontents") { out += `\n\n${TOC}\n\n`; continue; }
        if (["newpage", "clearpage", "pagebreak", "cleardoublepage"].includes(plain)) { index = optional(text, index)[1]; out += `\n\n${PAGE_BREAK}\n\n`; continue; }
        if (["par", "smallskip", "medskip", "bigskip"].includes(plain)) { out += "\n\n"; continue; }
        if (plain === "newline" || plain === "linebreak") { index = optional(text, index)[1]; out += "  \n"; continue; }
        if (plain === "today") { out += today(state.cjk); continue; }
        if (plain in SYMBOLS) { out += SYMBOLS[plain]; if (text[index] === "{" && text[index + 1] === "}") index += 2; continue; }
        if (plain === "textbf" || plain === "textit" || plain === "emph" || plain === "textsl" || plain === "underline" || plain === "uline" || plain === "textsc" || plain === "textrm" || plain === "textsf" || plain === "textnormal" || plain === "textup" || plain === "mbox" || plain === "text") {
          const [inner, after] = argument(text, index);
          const content = convert(inner, state).trim();
          const mark = plain === "textbf" ? "**" : (plain === "textit" || plain === "emph" || plain === "textsl") ? "*" : "";
          out += content ? `${mark}${content}${mark}` : "";
          index = after;
          continue;
        }
        if (plain === "texttt" || plain === "verb" || plain === "path") {
          if (plain === "verb") {
            const delimiter = text[index];
            const end = text.indexOf(delimiter, index + 1);
            out += "`" + text.slice(index + 1, end < 0 ? text.length : end) + "`";
            index = end < 0 ? text.length : end + 1;
            continue;
          }
          const [inner, after] = argument(text, index);
          const code = inner.replace(/\\([_&#%$\\{}])/g, "$1").replace(/\\textbackslash(\{\})?/g, "\\");
          out += code.includes("`") ? code : "`" + code + "`";
          index = after;
          continue;
        }
        if (plain === "textcolor" || plain === "colorbox" || plain === "fcolorbox") {
          // The colour goes, the text stays.
          let at = optional(text, index)[1];
          for (let skip = plain === "fcolorbox" ? 2 : 1; skip > 0; skip -= 1) at = argument(text, at)[1];
          const [inner, after] = argument(text, at);
          out += convert(inner, state);
          index = after;
          continue;
        }
        if (plain === "href") {
          const [url, afterUrl] = argument(text, index);
          const [label, after] = argument(text, afterUrl);
          out += `[${convert(label, state).trim()}](${url.trim().replace(/\\([#%_&])/g, "$1")})`;
          index = after;
          continue;
        }
        if (plain === "url") {
          const [url, after] = argument(text, index);
          const plainUrl = url.trim().replace(/\\([#%_&])/g, "$1");
          out += `[${plainUrl}](${plainUrl})`;
          index = after;
          continue;
        }
        if (plain === "footnote") {
          const [note, after] = argument(text, optional(text, index)[1]);
          state.footnotes.push(convert(note, state).trim());
          out += `[^${state.footnotes.length}]`;
          index = after;
          continue;
        }
        if (plain === "ref" || plain === "eqref" || plain === "autoref" || plain === "cref" || plain === "pageref") {
          const [name2, after] = argument(text, index);
          out += plain === "eqref" ? `(⁣⁣REF{${name2}}⁣⁣)` : `⁣⁣REF{${name2}}⁣⁣`;
          index = after;
          continue;
        }
        if (plain === "label") {
          const [name2, after] = argument(text, index);
          state.labels[name2] = float && state[float] ? String(state[float]) : state.lastNumber || "??";
          index = after;
          continue;
        }
        if (plain === "cite" || plain === "citep" || plain === "citet") {
          const [, afterNote] = optional(text, index);
          const [keys, after] = argument(text, afterNote);
          out += `[${keys.split(",").map((key) => key.trim()).join(", ")}]`;
          index = after;
          continue;
        }
        if (plain === "caption") {
          const [, afterShort] = optional(text, index);
          const [caption, after] = argument(text, afterShort);
          const kind = float || "figure";
          state[kind] += 1;
          const word = kind === "table" ? (state.cjk ? "表" : "Table") : (state.cjk ? "图" : "Figure");
          out += `\n\n*${word} ${state[kind]}${state.cjk ? "　" : ": "}${convert(caption, state).trim()}*\n\n`;
          index = after;
          continue;
        }
        if (plain === "includegraphics") {
          const [, afterOptions] = optional(text, index);
          const [file, after] = argument(text, afterOptions);
          out += `\n\n*（${state.cjk ? "图片" : "image"}：${file.trim()}）*\n\n`;
          index = after;
          continue;
        }
        if (plain === "item") { index = optional(text, index)[1]; out += "\n- "; continue; }
        if (plain === "and") { out += ", "; continue; }
        if (state.macros[`\\${plain}`] !== undefined && !/#\d/.test(state.macros[`\\${plain}`])) {
          out += convert(state.macros[`\\${plain}`], state);
          continue;
        }
        if (DROPPED.has(plain)) {
          // Its arguments go too: \vspace{1em}, \setlength{\parindent}{0pt}, \newcommand{\R}{…}.
          let at = optional(text, index)[1];
          const count = { setlength: 2, addtolength: 2, setcounter: 2, addtocounter: 2, fontsize: 2, newcommand: 2,
            renewcommand: 2, providecommand: 2, DeclareMathOperator: 2, newtheorem: 2, definecolor: 3 }[plain] || 1;
          for (let taken = 0; taken < count; taken += 1) {
            at = optional(text, at)[1];
            if (/^\s*[{\\]/.test(text.slice(at))) at = argument(text, at)[1];
          }
          if (plain === "newtheorem") at = optional(text, at)[1];
          index = at;
          continue;
        }
        if (IGNORED.has(plain)) continue;
        // Anything else: its text arguments are kept, the command itself goes.
        let at = optional(text, index)[1];
        while (text[at] === "{") {
          const [inner, after] = group(text, at);
          out += convert(inner, state);
          at = after;
        }
        index = at;
        continue;
      }
      if (character === "$") {
        const display = text[index + 1] === "$";
        const close = display ? "$$" : "$";
        let end = index + close.length;
        while (end < text.length && !(text.startsWith(close, end) && text[end - 1] !== "\\")) end += 1;
        const body = cleanMath(text.slice(index + close.length, end), state);
        state.pendingLabels = [];
        out += display ? `\n\n$$\n${body.trim()}\n$$\n\n` : `$${body}$`;
        index = end + close.length;
        continue;
      }
      if (character === "{") {
        const [inner, after] = group(text, index);
        const [styles, rest] = declarations(inner);
        out += styles.length ? styled(styles, convert(rest, state)) : convert(inner, state);
        index = after;
        continue;
      }
      if (character === "}") { index += 1; continue; }
      if (character === "~") { out += " "; index += 1; continue; }
      if (text.startsWith("``", index)) { out += "“"; index += 2; continue; }
      if (text.startsWith("''", index)) { out += "”"; index += 2; continue; }
      if (text.startsWith("---", index)) { out += "—"; index += 3; continue; }
      if (text.startsWith("--", index)) { out += "–"; index += 2; continue; }
      if (character === "*" || character === "<" || character === "|") { out += `\\${character}`; index += 1; continue; }
      out += character;
      index += 1;
    }
    return out;
  }

  /** The page's HTML for a create_pdf request ({ format, title, content }) and what it asks of the page. */
  function renderRequest(request, renderDocument) {
    const format = request.format || "markdown";
    let markdown = String(request.content || "");
    let macros = {};
    let page = {};
    if (format === "latex") {
      const converted = latexToMarkdown(markdown);
      markdown = converted.markdown;
      macros = converted.macros;
      page = converted.page;
    }
    if (request.title) markdown = `# ${String(request.title).replace(/\n+/g, " ")}\n\n${markdown}`;
    const html = renderDocument(markdown, macros)
      .replace(new RegExp(`<p>${PAGE_BREAK}</p>`, "g"), '<div class="page-break"></div>')
      .replace(new RegExp(`<p>${META}`, "g"), '<p class="meta">')
      .replace(new RegExp(`<p>${CENTER}`, "g"), '<p class="center">')
      .replace(/⁣STYLE:(\w+)⁣/g, '<span class="s-$1">')
      .replace(new RegExp(STYLE_END, "g"), "</span>");
    return { html, page };
  }

  function documentHtml(request, renderDocument) {
    return renderRequest(request, renderDocument).html;
  }

  /** Renders the request served at document.json, then waits for fonts; the result is in window.__pdfState. */
  async function start() {
    try {
      const request = await (await fetch("document.json", { cache: "no-store" })).json();
      // The language picks the CJK glyph forms (Simplified Chinese ones for Chinese text).
      document.documentElement.lang = /[㐀-鿿]/.test(String(request.content || "") + (request.title || "")) ? "zh-CN" : "en";
      document.body.className = `format-${request.format || "markdown"}`;
      const { html, page } = renderRequest(request, root.MobileUi.renderDocument);
      // The document's own \documentclass size and geometry margins win over the defaults.
      document.body.style.fontSize = `${page.fontPt || Number(request.font_size) || 12}pt`;
      const rules = [];
      if (page.margins) {
        const sides = ["top", "right", "bottom", "left"].filter((side) => side in page.margins);
        rules.push(`@page { ${sides.map((side) => `margin-${side}: ${page.margins[side].toFixed(1)}mm;`).join(" ")} }`);
        const width = 210 - (page.margins.left ?? 18) - (page.margins.right ?? 18);
        rules.push(`@media screen { body { width: ${width.toFixed(1)}mm; } }`);
      }
      if (request.format === "latex" && page.pageNumbers !== false) {
        rules.push('@page { @bottom-center { content: counter(page); font-family: "KaTeX_Main", serif; font-size: 10pt; } }');
      }
      if (rules.length) document.head.appendChild(Object.assign(document.createElement("style"), { textContent: rules.join("\n") }));
      document.getElementById("document").innerHTML = html;
      // Fonts load only once text needs them, which can be after "ready" resolved: load every face
      // first (KaTeX's are local and small), or the PDF may be printed in fallback fonts.
      void document.body.offsetHeight;
      await Promise.all(Array.from(document.fonts, (face) => face.load().catch(() => null)));
      await document.fonts.ready;
      await Promise.all([...document.images].map((image) => (image.complete ? null
        : new Promise((resolve) => { image.onload = image.onerror = resolve; }))));
      // A display formula wider than the page is scaled down to fit (printing would cut it off).
      for (const display of document.querySelectorAll(".katex-display")) {
        const formula = display.firstElementChild;
        if (formula && formula.scrollWidth > display.clientWidth) {
          formula.style.zoom = String(Math.max(0.45, display.clientWidth / formula.scrollWidth));
        }
      }
      const errors = document.querySelectorAll(".katex-error").length;
      const failedFonts = Array.from(document.fonts).filter((face) => face.status !== "loaded")
        .map((face) => `${face.family} ${face.weight} ${face.style}: ${face.status}`);
      root.__pdfState = { ok: true, math_errors: errors, fonts_not_loaded: failedFonts.slice(0, 30) };
    } catch (error) {
      root.__pdfState = { ok: false, error: String(error && error.message || error) };
    }
  }

  const api = { latexToMarkdown, documentHtml, renderRequest, start };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PdfTypeset = api;
})(typeof window !== "undefined" ? window : globalThis);
