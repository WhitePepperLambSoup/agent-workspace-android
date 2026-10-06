import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "../node_modules/esbuild/lib/main.js";

// Android owns its web tooling: run `npm ci` in "for Android/" (see package.json), never desktop/.
const root = path.dirname(fileURLToPath(import.meta.url));
const dependencies = path.resolve(root, "../node_modules");
const names = ["activity", "archive", "archive-restore", "arrow-down", "arrow-up", "battery-medium", "bell", "bot", "book-open", "brain", "calendar", "camera", "chart-no-axes-column", "check", "chevron-down", "chevron-left", "chevron-right", "circle-alert", "circle-check", "circle-plus", "circle-x", "clipboard-check", "clock", "code", "copy", "cpu", "database-backup", "download", "ellipsis", "eye", "file-text", "folder", "folder-open", "app-window", "bell-ring", "git-branch", "globe", "graduation-cap", "hand", "hard-drive", "heart", "history", "image-plus", "info", "languages", "layers", "lightbulb", "link", "list-checks", "list-todo", "loader-circle", "mail", "menu", "message-square-plus", "mic", "monitor-smartphone", "notebook-pen", "paperclip", "palette", "panel-left", "pause", "pencil", "play", "plus", "puzzle", "pin", "plane", "refresh-cw", "rotate-ccw", "save", "search", "send", "server", "settings", "share-2", "shield", "shopping-cart", "sparkles", "square", "square-pen", "star", "terminal", "trash-2", "upload", "user-round", "utensils", "wifi-off", "workflow", "wrench", "x", "zap"];
const icons = Object.fromEntries(await Promise.all(names.map(async (name) => {
  const module = await import(pathToFileURL(path.join(dependencies, "lucide-react/dist/esm/icons", `${name}.mjs`)).href);
  return [name, module.__iconNode];
})));
buildSync({
  entryPoints: [path.join(root, "vendor-entry.mjs")],
  nodePaths: [dependencies],
  outfile: path.join(root, "static/mobile-vendor.js"),
  bundle: true,
  minify: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  legalComments: "inline",
  define: { __MOBILE_ICON_NODES__: JSON.stringify(icons) },
});
// Diagrams are a separate, much larger file that app.js loads only when a reply contains one.
buildSync({
  entryPoints: [path.join(root, "mermaid-entry.mjs")],
  nodePaths: [dependencies],
  outfile: path.join(root, "static/mobile-mermaid.js"),
  bundle: true,
  minify: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  legalComments: "inline",
});
const packages = ["unified", "remark-parse", "remark-gfm", "remark-math", "remark-rehype", "rehype-sanitize", "rehype-katex", "katex", "hast-util-to-html", "lucide-react", "mermaid"];
const licenses = await Promise.all(packages.map(async (name) => {
  const packageRoot = path.join(dependencies, name);
  const metadata = JSON.parse(await readFile(path.join(packageRoot, "package.json"), "utf8"));
  let license;
  for (const filename of ["license", "LICENSE", "LICENSE.md"]) {
    try { license = await readFile(path.join(packageRoot, filename), "utf8"); break; } catch {}
  }
  // Some packages (remark-math) publish no license file; their package.json still names the license.
  if (!license && metadata.license) license = `License: ${metadata.license} (declared in package.json; the npm package ships no license file)`;
  if (!license) throw new Error(`Missing license for ${name}`);
  return `${name} ${metadata.version}\n${license.trim()}`;
}));
await writeFile(path.join(root, "static/mobile-vendor.LICENSE.txt"), `${licenses.join("\n\n")}\n`);
console.log("Bundled offline Markdown, math, Lucide icons and the on-demand diagram renderer.");
