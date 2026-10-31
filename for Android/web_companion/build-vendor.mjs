import { copyFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "../node_modules/esbuild/lib/main.js";

// Android owns its web tooling: run `npm ci` in "for Android/" (see package.json), never desktop/.
const root = path.dirname(fileURLToPath(import.meta.url));
const dependencies = path.resolve(root, "../node_modules");
const names = ["activity", "archive", "archive-restore", "arrow-down", "arrow-up", "battery-medium", "bell", "bot", "book-open", "brain", "building-2", "calendar", "camera", "chart-no-axes-column", "check", "chevron-down", "chevron-left", "chevron-right", "circle-alert", "circle-check", "circle-plus", "circle-x", "clipboard-check", "clock", "code", "copy", "cpu", "database-backup", "download", "ellipsis", "eye", "file-text", "folder", "folder-open", "app-window", "bell-ring", "git-branch", "globe", "graduation-cap", "hand", "hard-drive", "heart", "history", "image-plus", "info", "languages", "layers", "lightbulb", "link", "list-checks", "list-todo", "loader-circle", "log-out", "mail", "menu", "message-square-plus", "mic", "monitor-smartphone", "notebook-pen", "paperclip", "palette", "panel-left", "pause", "pencil", "phone", "play", "plus", "puzzle", "pin", "plane", "refresh-cw", "rotate-ccw", "save", "search", "send", "server", "settings", "share-2", "shield", "shield-check", "shopping-cart", "sparkles", "square", "square-pen", "star", "terminal", "trash-2", "upload", "user-round", "users", "utensils", "volume-2", "wifi-off", "workflow", "wrench", "x", "zap", "crosshair", "map", "construction"];
const icons = Object.fromEntries(await Promise.all(names.map(async (name) => {
  const file = path.join(dependencies, "lucide-react/dist/esm/icons", `${name}.mjs`);
  let module = await import(pathToFileURL(file).href);
  if (!module.__iconNode) {
    // A renamed icon (history → rotate-ccw-clock) only re-exports the new one.
    const renamed = (await readFile(file, "utf8")).match(/from '\.\/([a-z0-9-]+)\.mjs'/)?.[1];
    if (renamed) module = await import(pathToFileURL(path.join(path.dirname(file), `${renamed}.mjs`)).href);
  }
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
// The expert team's studio (three.js and the office scene, web_companion/studio) is loaded only when
// it opens, like the diagrams.
buildSync({
  entryPoints: [path.join(root, "studio/entry.ts")],
  nodePaths: [dependencies],
  outfile: path.join(root, "static/mobile-studio.js"),
  bundle: true,
  minify: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  legalComments: "inline",
});
// create_pdf typesets with KaTeX's HTML output, which needs its stylesheet and fonts (woff2 only:
// every Chromium WebView reads it).
const katexDist = path.join(dependencies, "katex/dist");
const pdfFonts = path.join(root, "pdf/fonts");
await mkdir(pdfFonts, { recursive: true });
const css = (await readFile(path.join(katexDist, "katex.min.css"), "utf8"))
  .replace(/,url\(fonts\/[^)]+\.woff\) format\("woff"\)|,url\(fonts\/[^)]+\.ttf\) format\("truetype"\)/g, "");
await writeFile(path.join(root, "pdf/katex.min.css"), css);
for (const name of await readdir(path.join(katexDist, "fonts"))) {
  if (name.endsWith(".woff2")) await copyFile(path.join(katexDist, "fonts", name), path.join(pdfFonts, name));
}
const packages = ["unified", "remark-parse", "remark-gfm", "remark-math", "remark-rehype", "rehype-sanitize", "rehype-katex", "katex", "hast-util-to-html", "lucide-react", "mermaid", "three"];
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
console.log("Bundled offline Markdown, math, Lucide icons, the on-demand diagram renderer and the studio.");
