import { build } from "esbuild";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { existsSync, statSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const isWatch = process.argv.includes("--watch");

const outDir = resolve(__dirname, "..", "src", "trade_advisor", "web", "static");
const entryPoint = resolve(__dirname, "bridge.ts");

const MAX_TOTAL_KB = 75;

if (!existsSync(entryPoint)) {
  console.error(`Entry point not found: ${entryPoint}`);
  process.exit(1);
}

const buildOptions = {
  entryPoints: [entryPoint],
  outdir: outDir,
  bundle: true,
  minify: !isWatch,
  sourcemap: isWatch,
  format: "esm",
  target: ["es2020"],
  jsx: "automatic",
  jsxImportSource: "preact",
  external: [],
  logLevel: "info",
};

function checkBundleSizes() {
  const bundlePath = resolve(outDir, "bridge.js");
  if (!existsSync(bundlePath)) {
    console.error("Build output not found: bridge.js");
    process.exit(1);
  }
  const bytes = statSync(bundlePath).size;
  const kb = bytes / 1024;
  console.log(`  bridge.js: ${kb.toFixed(1)} KB`);
  if (kb > MAX_TOTAL_KB) {
    console.error(`Total JS budget exceeded: ${kb.toFixed(1)} KB > ${MAX_TOTAL_KB} KB`);
    process.exit(1);
  }
  console.log(`  Total: ${kb.toFixed(1)} KB (budget: ${MAX_TOTAL_KB} KB) ✓`);
}

if (isWatch) {
  const ctx = await build({
    ...buildOptions,
    plugins: [
      {
        name: "watch-plugin",
        setup(build) {
          build.onEnd((result) => {
            console.log(
              `Build completed at ${new Date().toLocaleTimeString()}, errors: ${result.errors.length}`
            );
          });
        },
      },
    ],
  });
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  const result = await build(buildOptions);
  if (result.errors.length > 0) {
    console.error("Build failed with errors");
    process.exit(1);
  }
  console.log("Build complete.");
  checkBundleSizes();
}
