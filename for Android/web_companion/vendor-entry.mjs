import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeSanitize from "rehype-sanitize";
import { toHtml } from "hast-util-to-html";

const renderer = unified().use(remarkParse).use(remarkGfm).use(remarkRehype).use(rehypeSanitize);
const iconNodes = __MOBILE_ICON_NODES__;
const escapeAttribute = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);

window.MobileUi = {
  renderMarkdown(text) {
    return toHtml(renderer.runSync(renderer.parse(String(text || ""))));
  },
  iconMarkup(name) {
    const children = (iconNodes[name] || []).map(([tag, attributes]) => {
      const values = Object.entries(attributes).filter(([key]) => key !== "key").map(([key, value]) => `${key}="${escapeAttribute(value)}"`).join(" ");
      return `<${tag} ${values}></${tag}>`;
    }).join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${children}</svg>`;
  },
};
