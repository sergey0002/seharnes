#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function findProjectRoot(start) {
  let dir = start;
  for (;;) {
    if (fs.existsSync(path.join(dir, ".cursor")) || fs.existsSync(path.join(dir, ".git"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      throw new Error("php-docker: project root not found");
    }
    dir = parent;
  }
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = findProjectRoot(scriptDir);
const container = process.env.DOCKER_PHP_CONTAINER || "copytrust-dev-php-apache-1";

function toLinuxArg(arg) {
  const normalized = path.normalize(arg);
  if (normalized.toLowerCase().startsWith(repoRoot.toLowerCase())) {
    return `/var/www/html${normalized.slice(repoRoot.length).replace(/\\/g, "/")}`;
  }
  return arg.replace(/\\/g, "/");
}

const args = process.argv.slice(2).map(toLinuxArg);
const result = spawnSync("docker", ["exec", "-i", container, "php", ...args], {
  stdio: "inherit",
});
process.exit(result.status ?? 1);
