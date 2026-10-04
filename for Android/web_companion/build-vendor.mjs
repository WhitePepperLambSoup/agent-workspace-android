import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildSync } from "../node_modules/esbuild/lib/main.js";

// Android owns its web tooling: run `npm ci` in "for Android/" (see package.json), never desktop/.
const root = path.dirname(fileURLToPath(import.meta.url));
const dependencies = path.resolve(root, "../node_modules");
const names = ["activity", "archive", "archive-restore", "arrow-down", "arrow-up", "battery-medium", "bell", "bot", "brain", "chart-no-axes-column", "check", "chevron-down", "chevron-left", "chevron-right", "circle-alert", "circle-check", "circle-plus", "circle-x", "clipboard-check", "clock", "copy", "cpu", "download", "ellipsis", "eye", "file-text", "folder", "folder-open", "git-branch", "globe", "hand", "hard-drive", "history", "image-plus", "info", "languages", "layers", "link", "list-checks", "loader-circle", "menu", "message-square-plus", "mic", "monitor-smartphone", "paperclip", "palette", "panel-left", "pause", "pencil", "play", "plus", "puzzle", "refresh-cw", "save", "search", "send", "settings", "share-2", "shield", "sparkles", "square", "square-pen", "terminal", "trash-2", "wifi-off", "workflow", "wrench", "x"];
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
const packages = ["unified", "remark-parse", "remark-gfm", "remark-rehype", "rehype-sanitize", "hast-util-to-html", "lucide-react"];
const licenses = await Promise.all(packages.map(async (name) => {
  const packageRoot = path.join(dependencies, name);
  const metadata = JSON.parse(await readFile(path.join(packageRoot, "package.json"), "utf8"));
  let license;
  for (const filename of ["license", "LICENSE", "LICENSE.md"]) {
    try { license = await readFile(path.join(packageRoot, filename), "utf8"); break; } catch {}
  }
  if (!license) throw new Error(`Missing license for ${name}`);
  return `${name} ${metadata.version}\n${license.trim()}`;
}));
await writeFile(path.join(root, "static/mobile-vendor.LICENSE.txt"), `${licenses.join("\n\n")}\n`);
console.log("Bundled offline Markdown and Lucide icons.");
