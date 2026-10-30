import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkRehype from "remark-rehype";
import rehypeSanitize from "rehype-sanitize";
import rehypeKatex from "rehype-katex";
import { toHtml } from "hast-util-to-html";

// Raw HTML in a message ("add rules before </style>") is shown as the text it is. remark-rehype
// drops raw HTML nodes, which made tags vanish from both user and assistant messages.
function rawHtmlAsText() {
  const blocks = new Set(["root", "blockquote", "listItem"]);
  const visit = (node) => {
    node.children = (node.children || []).map((child) => {
      if (child.type !== "html") return visit(child);
      // Models write <br> for line breaks inside table cells; keep that one as a break.
      if (!blocks.has(node.type) && /^<br\s*\/?>$/i.test(child.value)) return { type: "break", position: child.position };
      const text = { type: "text", value: child.value, position: child.position };
      return blocks.has(node.type) ? { type: "paragraph", children: [text], position: child.position } : text;
    });
    return node;
  };
  return visit;
}

// Math runs after sanitizing: the sanitizer keeps the `language-math` class remark-math emits, and
// KaTeX's own output is never stripped. MathML needs no fonts or stylesheet; Chromium draws it.
const renderer = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(rawHtmlAsText)
  .use(remarkRehype)
  .use(rehypeSanitize)
  .use(rehypeKatex, { output: "mathml", strict: "ignore" });
const iconNodes = __MOBILE_ICON_NODES__;
const escapeAttribute = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

// Models often write LaTeX as \( … \) and \[ … \], which Markdown math does not recognise, and put
// display formulas on one line as $$ … $$ (which Markdown treats as inline). Rewrite both to the
// forms remark-math expects, leaving fenced and inline code untouched.
function normalizeMath(text) {
  return String(text || "").split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g).map((part, index) => index % 2 ? part : escapeMoney(part
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, body) => `\n$$\n${body.trim()}\n$$\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, body) => `$${body.trim()}$`)
    .replace(/^([ \t]*)\$\$([^\n]+?)\$\$[ \t]*$/gm, (_, indent, body) => `${indent}$$\n${indent}${body.trim()}\n${indent}$$`))).join("");
}

// A single "$" is a formula's edge only as pandoc reads it: an opening one has no space after it, and
// the next "$" closes it if it has no space before it and no digit after it, in the same paragraph (a
// formula holds no bare "$"). Any other "$" is money ("A$40,000 … A$40k", "$5 and $10") and is
// escaped, or the text between two prices turned into one italic formula. "$$" is left as it is.
function escapeMoney(part) {
  const singles = [];
  for (let at = 0; at < part.length; at += 1) {
    if (part[at] === "\\") { at += 1; continue; }
    if (part[at] !== "$") continue;
    if (part[at + 1] === "$") { at += 1; continue; }
    singles.push(at);
  }
  const formula = new Set();
  for (let index = 0; index + 1 < singles.length; index += 1) {
    const open = singles[index];
    const close = singles[index + 1];
    if (!part[open + 1] || /\s/.test(part[open + 1]) || /\n[ \t]*\n/.test(part.slice(open, close))) continue;
    if (/\s/.test(part[close - 1]) || /\d/.test(part[close + 1] || "")) continue;
    formula.add(open).add(close);
    index += 1;
  }
  let escaped = "";
  let from = 0;
  for (const at of singles) {
    if (formula.has(at)) continue;
    escaped += `${part.slice(from, at)}\\$`;
    from = at + 1;
  }
  return escaped + part.slice(from);
}

window.MobileUi = {
  renderMarkdown(text) {
    return toHtml(renderer.runSync(renderer.parse(normalizeMath(text))));
  },
  // PDFs (create_pdf): KaTeX's HTML output with its own fonts looks like LaTeX on every WebView
  // version and prints exactly; `macros` carries a LaTeX document's \newcommand definitions.
  renderDocument(text, macros = {}) {
    const documentRenderer = unified()
      .use(remarkParse)
      .use(remarkGfm)
      .use(remarkMath)
      .use(rawHtmlAsText)
      .use(remarkRehype)
      .use(rehypeSanitize)
      .use(rehypeKatex, { output: "html", strict: "ignore", macros: { ...macros } });
    return toHtml(documentRenderer.runSync(documentRenderer.parse(normalizeMath(text))));
  },
  iconMarkup(name) {
    const children = (iconNodes[name] || []).map(([tag, attributes]) => {
      const values = Object.entries(attributes).filter(([key]) => key !== "key").map(([key, value]) => `${key}="${escapeAttribute(value)}"`).join(" ");
      return `<${tag} ${values}></${tag}>`;
    }).join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${children}</svg>`;
  },
};
