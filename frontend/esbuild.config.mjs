import { build } from "esbuild";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const isWatch = process.argv.includes("--watch");

const outDir = resolve(__dirname, "..", "src", "trade_advisor", "web", "static");

const entryPoints = [resolve(__dirname, "islands", "dataQualityBadge.tsx")];

const buildOptions = {
  entryPoints,
  outdir: outDir,
  bundle: true,
  minify: !isWatch,
  sourcemap: isWatch,
  format: "esm" as const,
  target: ["es2020"],
  jsx: "automatic" as const,
  jsxImportSource: "preact",
  external: [],
  logLevel: "info" as const,
};

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
  await build(buildOptions);
  console.log("Build complete.");
}
