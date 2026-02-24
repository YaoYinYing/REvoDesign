/*
 * Collect all Python source files under src/REvoDesign into program.docx.
 * This utility intentionally delegates traversal/read operations to shell tools
 * to avoid ad-hoc filesystem handling logic in Node.
 */
const { spawnSync } = require("child_process");

const command = [
  "find ./src/REvoDesign -type f -name '*.py' -print0",
  "xargs -0 cat > ./program.docx",
].join(" | ");

const result = spawnSync("bash", ["-lc", command], { stdio: "inherit" });
if (result.status !== 0) {
  process.exit(result.status || 1);
}
