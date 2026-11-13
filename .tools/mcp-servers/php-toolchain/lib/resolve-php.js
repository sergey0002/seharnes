import { existsSync, readdirSync } from "node:fs";
import path from "node:path";

function phpFromLaragonRoot(root) {
  const phpDir = path.join(root, "bin", "php");
  if (!existsSync(phpDir)) return null;
  const dirs = readdirSync(phpDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && d.name.startsWith("php-"))
    .map((d) => d.name)
    .sort()
    .reverse();
  for (const dir of dirs) {
    const candidate = path.join(phpDir, dir, process.platform === "win32" ? "php.exe" : "php");
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export function resolvePhpBin() {
  if (process.env.PHP_BIN && existsSync(process.env.PHP_BIN)) {
    return process.env.PHP_BIN;
  }
  if (process.env.LARAGON_ROOT) {
    const fromRoot = phpFromLaragonRoot(process.env.LARAGON_ROOT);
    if (fromRoot) return fromRoot;
  }
  return "php";
}

export function workspaceRoot() {
  return process.env.MCP_WORKSPACE || process.cwd();
}
