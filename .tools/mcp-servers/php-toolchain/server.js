#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { existsSync } from "node:fs";
import path from "node:path";
import { resolvePhpBin, workspaceRoot } from "./lib/resolve-php.js";
import { cursorToolsDir, runPhp, runProcess, resolveVendorBin } from "./lib/run.js";

const MODE = (process.env.MCP_PHP_TOOLCHAIN_MODE || "all").toLowerCase();

function modesInclude(...allowed) {
  if (MODE === "all") return true;
  return allowed.includes(MODE);
}

const server = new McpServer({
  name: "php-toolchain",
  version: "1.0.0",
});

if (modesInclude("phpstan")) {
  const phpstanMissing = (root) => ({
    content: [
      {
        type: "text",
        text:
          `PHPStan not found.\n` +
          `Run: .\\.cursor\\setup.ps1\n` +
          `Or: cd .cursor/tools && composer install\n` +
          `Project: ${root}`,
      },
    ],
    isError: true,
  });

  server.registerTool(
    "phpstan_analyze",
    {
      description:
        "Run PHPStan on PHP files changed by a task or on explicit paths. The stand runs PHP 7.1, so the kit phar runs under PHP 7.4 Docker with phpVersion 70100.",
      inputSchema: {
        task: z
          .number()
          .int()
          .positive()
          .optional()
          .describe(
            "Task number: analyze only PHP files changed by this task from .doc/tasks/{N}/diff.files.md and git"
          ),
        paths: z
          .array(z.string())
          .optional()
          .describe("Explicit paths relative to project root"),
        level: z.number().int().min(0).max(9).optional().describe("PHPStan level, default 0"),
      },
    },
    async ({ task, paths, level }) => {
      const root = workspaceRoot();
      const phpstan = resolveVendorBin("phpstan");
      if (!existsSync(phpstan)) return phpstanMissing(root);

      if (task !== undefined) {
        const script = path.join(root, ".cursor", "scripts", "phpstan-task.sh");
        const result = await runProcess(
          "bash",
          [script, String(task), String(level ?? 0)],
          { cwd: root }
        );
        const text = [result.stdout, result.stderr].filter(Boolean).join("\n");
        return {
          content: [{ type: "text", text: text || `(exit ${result.code})` }],
          isError: result.code !== 0,
        };
      }

      if (!paths?.length) {
        return {
          content: [
            {
              type: "text",
              text:
                "Pass task=<N> to analyze PHP files changed by the task, or paths=[...] for explicit files.",
            },
          ],
          isError: true,
        };
      }

      const args = ["analyze", "--error-format=json", "--no-progress"];
      if (process.env.PHPSTAN_DOCKER_IMAGE) {
        args.push("-c", "/app/.cursor/tools/phpstan.neon");
      }
      if (level !== undefined) args.push(`--level=${level}`);
      else if (!process.env.PHPSTAN_DOCKER_IMAGE) args.push("--level=0");
      args.push(...paths);

      const result = process.env.PHPSTAN_DOCKER_IMAGE
        ? await runProcess(
            "bash",
            [path.join(root, ".cursor", "scripts", "phpstan-docker.sh"), ...args],
            { cwd: root }
          )
        : await runPhp([phpstan, ...args], [], { cwd: root });
      const text = [result.stdout, result.stderr].filter(Boolean).join("\n");
      return {
        content: [{ type: "text", text: text || `(exit ${result.code})` }],
        isError: result.code !== 0,
      };
    }
  );
}

if (modesInclude("php-deps", "deps", "phpcallgraph", "phpda")) {
  server.registerTool(
    "phpcallgraph_generate",
    {
      description:
        "Generate PHP call graph (SVG/PNG) via phpcallgraph PHAR or composer binary.",
      inputSchema: {
        sourcePath: z
          .string()
          .default("src")
          .describe("Directory to scan (relative to workspace)"),
        outputFile: z
          .string()
          .default(".cursor/artifacts/callgraph.svg")
          .describe("Output file path (relative to workspace)"),
        format: z.enum(["svg", "png", "dot"]).default("svg"),
        ignorePattern: z
          .string()
          .default("/(vendor|tests|node_modules|storage|bootstrap/cache)/")
          .optional(),
      },
    },
    async ({ sourcePath, outputFile, format, ignorePattern }) => {
      const root = workspaceRoot();
      const out = path.join(root, outputFile);
      const src = path.join(root, sourcePath);
      const phar = path.join(cursorToolsDir(), "phpcallgraph.phar");
      const pharProject = [
        path.join(root, ".tools", "phpcallgraph.phar"),
        path.join(root, "tools", "phpcallgraph.phar"),
      ].find(existsSync);
      const vendor = resolveVendorBin("phpcallgraph");

      let cmd;
      let args;
      if (pharProject) {
        cmd = resolvePhpBin();
        args = [
          pharProject,
          "-r",
          "-f",
          format,
          "-o",
          out,
          ...(ignorePattern ? ["-i", ignorePattern] : []),
          src,
        ];
      } else if (existsSync(phar)) {
        cmd = resolvePhpBin();
        args = [
          phar,
          "-r",
          "-f",
          format,
          "-o",
          out,
          ...(ignorePattern ? ["-i", ignorePattern] : []),
          src,
        ];
      } else if (existsSync(vendor)) {
        cmd = resolvePhpBin();
        args = [
          vendor,
          "-r",
          "-f",
          format,
          "-o",
          out,
          ...(ignorePattern ? ["-i", ignorePattern] : []),
          src,
        ];
      } else {
        return {
          content: [
            {
              type: "text",
              text:
                "phpcallgraph not found.\n" +
                "  Place phpcallgraph.phar in .cursor/tools/ or project .tools/\n" +
                "  Or: composer require --dev phpcallgraph/phpcallgraph in the project",
            },
          ],
          isError: true,
        };
      }

      const result = await runProcess(cmd, args, { cwd: root });
      const msg = [
        `exit: ${result.code}`,
        `output: ${out}`,
        result.stdout,
        result.stderr,
      ]
        .filter(Boolean)
        .join("\n");
      return {
        content: [{ type: "text", text: msg }],
        isError: result.code !== 0,
      };
    }
  );

  server.registerTool(
    "phpda_analyze",
    {
      description:
        "Run mamuz/php-dependency-analysis (class dependency graph / violations).",
      inputSchema: {
        configFile: z
          .string()
          .default("phpda.xml")
          .describe("phpda config file in project root"),
      },
    },
    async ({ configFile }) => {
      const root = workspaceRoot();
      const bin = resolveVendorBin("phpda");
      if (!existsSync(bin)) {
        return {
          content: [
            {
              type: "text",
              text:
                "phpda not found.\n" +
                "Run: .\\.cursor\\setup.ps1\n" +
                "Or: cd .cursor/tools && composer install",
            },
          ],
          isError: true,
        };
      }
      const cfgCandidates = [
        path.join(root, configFile),
        path.join(cursorToolsDir(), "phpda.yml"),
        path.join(cursorToolsDir(), "phpda.yml.example"),
      ];
      const cfg = cfgCandidates.find((p) => existsSync(p));
      const args = cfg ? [bin, cfg] : [bin];
      const result = await runPhp(args, [], { cwd: root });
      const text = [result.stdout, result.stderr].filter(Boolean).join("\n");
      return {
        content: [{ type: "text", text: text || `(exit ${result.code})` }],
        isError: result.code !== 0,
      };
    }
  );
}

const transport = new StdioServerTransport();
await server.connect(transport);
