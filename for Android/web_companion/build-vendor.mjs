import { copyFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "../node_modules/esbuild/lib/main.js";
import { BUNDLES, writeVendorLicenses } from "./vendor-licenses.mjs";

// Android owns its web tooling: run `npm ci` in "for Android/" (see package.json), never desktop/.
const root = path.dirname(fileURLToPath(import.meta.url));
const dependencies = path.resolve(root, "../node_modules");
const names = ["activity", "archive", "archive-restore", "arrow-down", "arrow-up", "battery-medium", "bell", "bot", "book-open", "brain", "building-2", "calendar", "calendar-clock", "clapperboard", "camera", "chart-no-axes-column", "check", "chevron-down", "chevron-left", "chevron-right", "circle-alert", "circle-check", "circle-plus", "circle-x", "clipboard-check", "clock", "code", "copy", "cpu", "database-backup", "download", "ellipsis", "eye", "file-text", "folder", "folder-open", "app-window", "bell-ring", "git-branch", "globe", "graduation-cap", "hand", "hard-drive", "heart", "history", "image-plus", "info", "languages", "layers", "lightbulb", "link", "list-checks", "list-todo", "loader-circle", "log-out", "mail", "menu", "message-square-plus", "mic", "monitor-smartphone", "notebook-pen", "paperclip", "palette", "panel-left", "pause", "pencil", "phone", "play", "plus", "puzzle", "pin", "plane", "refresh-cw", "rotate-ccw", "save", "search", "send", "server", "settings", "share-2", "shield", "shield-check", "shopping-cart", "sparkles", "square", "square-pen", "star", "terminal", "trash-2", "upload", "user-round", "users", "utensils", "volume-2", "wifi-off", "workflow", "wrench", "x", "zap", "crosshair", "map", "construction"];
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
// The page's bundles (vendor-licenses.mjs): Markdown, math and icons; the diagrams, a separate, much
// larger file that app.js loads only when a reply contains one; and the expert team's studio
// (three.js and the office scene, web_companion/studio), also loaded only when it opens.
const metafiles = BUNDLES.map((bundle, index) => buildSync({
  ...bundle,
  metafile: true,
  ...(index === 0 ? { define: { __MOBILE_ICON_NODES__: JSON.stringify(icons) } } : {}),
}).metafile);
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
await writeVendorLicenses(metafiles);
console.log("Bundled offline Markdown, math, Lucide icons, the on-demand diagram renderer and the studio.");
