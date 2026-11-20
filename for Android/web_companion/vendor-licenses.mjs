import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// The license texts of every npm package inside the page's bundles (mobile-vendor.js,
// mobile-mermaid.js, mobile-studio.js), read from node_modules as esbuild reports what it bundled.
// It used to list twelve top-level packages only: the d3 modules, dagre, cytoscape, lodash-es,
// DOMPurify and the rest that mermaid pulls in had no license text, and BSD-3-Clause and
// Apache-2.0 require one with the binary. Nothing is downloaded; a package with no license file
// on disk is listed as missing, with the license its package.json declares.

const root = path.dirname(fileURLToPath(import.meta.url));
const dependencies = path.resolve(root, "../node_modules");

// What build-vendor.mjs bundles (it adds the icon data to the first one).
export const BUNDLES = [
  { entryPoints: [path.join(root, "vendor-entry.mjs")], outfile: path.join(root, "static/mobile-vendor.js") },
  { entryPoints: [path.join(root, "mermaid-entry.mjs")], outfile: path.join(root, "static/mobile-mermaid.js") },
  { entryPoints: [path.join(root, "studio/entry.ts")], outfile: path.join(root, "static/mobile-studio.js") },
].map((bundle) => ({
  ...bundle,
  nodePaths: [dependencies],
  bundle: true,
  minify: true,
  format: "iife",
  platform: "browser",
  target: "es2020",
  legalComments: "inline",
}));

// Taken in without esbuild seeing them: Lucide's icon data (read by build-vendor.mjs) and KaTeX's
// stylesheet and fonts (copied for create_pdf).
const EMBEDDED = ["lucide-react", "katex"];
const LICENSE_FILE = /^(licen[cs]e|copying|notice)(\.(md|txt|markdown))?$|^(licen[cs]e|copying)[-.]/i;

/** The packages under node_modules that the bundles' inputs come from. */
export function bundledPackages(metafiles) {
  const found = new Set(EMBEDDED);
  for (const metafile of metafiles) {
    for (const input of Object.keys(metafile.inputs)) {
      const parts = input.replace(/\\/g, "/").split("/");
      const at = parts.lastIndexOf("node_modules");
      if (at < 0 || at + 1 >= parts.length) continue;
      found.add(parts[at + 1].startsWith("@") ? `${parts[at + 1]}/${parts[at + 2]}` : parts[at + 1]);
    }
  }
  return [...found].sort();
}

/** Writes static/mobile-vendor.LICENSE.txt; returns the packages whose license text is missing. */
export async function writeVendorLicenses(metafiles) {
  const sections = [];
  const missing = [];
  for (const name of bundledPackages(metafiles)) {
    const packageRoot = path.join(dependencies, name);
    const metadata = JSON.parse(await readFile(path.join(packageRoot, "package.json"), "utf8"));
    const files = (await readdir(packageRoot)).filter((file) => LICENSE_FILE.test(file)).sort();
    const texts = await Promise.all(files.map(async (file) => (await readFile(path.join(packageRoot, file), "utf8")).trim()));
    const declared = typeof metadata.license === "string" ? metadata.license : metadata.license?.type || "not declared";
    if (!texts.length) {
      missing.push(`${name} ${metadata.version} (package.json declares: ${declared})`);
      continue;
    }
    sections.push(`${name} ${metadata.version}\n${texts.join("\n\n")}`);
  }
  const report = missing.length
    ? `\n\nPackages in the bundles whose npm package ships no license file (the license their package.json declares):\n${missing.map((line) => `- ${line}`).join("\n")}`
    : "";
  await writeFile(path.join(root, "static/mobile-vendor.LICENSE.txt"), `${sections.join("\n\n")}${report}\n`);
  return missing;
}

// Run by itself (node web_companion/vendor-licenses.mjs): the bundles are worked out in memory, not
// written, and only the license file is.
if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  const { buildSync } = await import(pathToFileURL(path.join(dependencies, "esbuild/lib/main.js")).href);
  const metafiles = BUNDLES.map((bundle) => buildSync({ ...bundle, write: false, metafile: true }).metafile);
  const missing = await writeVendorLicenses(metafiles);
  console.log(`Wrote the license texts of ${bundledPackages(metafiles).length - missing.length} packages; ${missing.length} ship none.`);
}
