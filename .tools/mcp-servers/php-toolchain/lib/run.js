import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { resolvePhpBin, workspaceRoot } from "./resolve-php.js";

export function cursorToolsDir() {
  return path.join(workspaceRoot(), ".cursor", "tools");
}

/** Project vendor/bin first, then .cursor/tools/vendor/bin */
export function resolveVendorBin(name) {
  const bases = [
    path.join(workspaceRoot(), "vendor", "bin"),
    path.join(cursorToolsDir(), "vendor", "bin"),
  ];
  for (const base of bases) {
    for (const candidate of [path.join(base, name), path.join(base, `${name}.bat`)]) {
      if (existsSync(candidate)) return candidate;
    }
  }
  return path.join(workspaceRoot(), "vendor", "bin", name);
}

export function runProcess(command, args, options = {}) {
  const cwd = options.cwd || workspaceRoot();
  const env = { ...process.env, ...options.env };
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env,
      shell: false,
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr, cwd, command, args });
    });
  });
}

export async function runPhp(scriptOrArgs, extraArgs = [], options = {}) {
  const php = resolvePhpBin();
  const args = Array.isArray(scriptOrArgs)
    ? scriptOrArgs
    : [scriptOrArgs, ...extraArgs];
  return runProcess(php, args, options);
}

/** @deprecated use resolveVendorBin */
export function vendorBin(name) {
  return resolveVendorBin(name);
}
