import mermaid from "mermaid";

// Loaded only when a finished reply contains a ```mermaid block (the library is large).
// "strict" keeps diagram labels sanitized and disables click handlers and scripts.
let theme = null;
let counter = 0;

window.MobileMermaid = {
  async render(source, dark) {
    const wanted = dark ? "dark" : "default";
    if (wanted !== theme) {
      mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: wanted });
      theme = wanted;
    }
    counter += 1;
    const { svg } = await mermaid.render(`agent-mermaid-${counter}`, String(source || ""));
    return svg;
  },
};
