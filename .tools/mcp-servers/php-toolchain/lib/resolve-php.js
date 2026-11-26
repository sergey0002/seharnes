import { existsSync, readdirSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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
  const root = realpathSync(fileURLToPath(new URL("../../../../", import.meta.url)));
  const cwd = realpathSync(process.cwd());
  if (cwd !== root) {
    throw new Error("PHP MCP requires cwd at its local installation root");
  }
  const configured = process.env.MCP_WORKSPACE;
  if (configured && realpathSync(configured) !== root) {
    throw new Error("PHP MCP rejects MCP_WORKSPACE outside its local installation");
  }
  return root;
}

workspaceRoot();
