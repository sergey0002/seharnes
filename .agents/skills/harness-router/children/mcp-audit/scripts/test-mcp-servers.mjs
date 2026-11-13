#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import net from "node:net";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(scriptDir, "../../../../../../");
const mcpJsonPath = path.join(workspace, ".cursor", "mcp.json");
const envFile = path.join(workspace, ".cursor", "mcp.env");

function loadEnvFile() {
  const env = { ...process.env, MCP_WORKSPACE: workspace };
  try {
    for (const line of readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const i = t.indexOf("=");
      if (i === -1) continue;
      env[t.slice(0, i).trim()] = t.slice(i + 1).trim();
    }
  } catch {}
  return env;
}

function interpolate(value, env) {
  if (typeof value !== "string") return value;
  return value
    .replace(/\$\{workspaceFolder\}/g, workspace)
    .replace(/\$\{userHome\}/g, process.env.USERPROFILE || process.env.HOME || "")
    .replace(/\$\{env:([^}]+)\}/g, (_, k) => env[k] ?? process.env[k] ?? "");
}

const messages = [
  {
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "mcp-smoke-test", version: "1.0" },
    },
  },
  { jsonrpc: "2.0", method: "notifications/initialized" },
  { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} },
];

// Servers outside the harness scope: never probed, reported as SKIP.
// Source: mcp_harness_scope project memory (xdebug excluded,
// disabled servers stay disabled).
const OUT_OF_SCOPE = new Set(["xdebug"]);

// Some stdio servers (PHP McpStdioServer) use HTTP-style Content-Length
// framing instead of bare newline-delimited JSON-RPC.
function frameMessage(obj) {
  const body = JSON.stringify(obj);
  return `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`;
}

function extractTools(stdout) {
  const names = [...stdout.matchAll(/"name"\s*:\s*"([^"]+)"/g)].map((m) => m[1]);
  const serverNames = new Set(["codebase-memory-mcp", "mcp-git", "jira-task-mcp", "php-toolchain", "mysql-server", "xdebug-mcp"]);
  return names.filter((n) => !serverNames.has(n));
}

function parseMcpPayload(text) {
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6));
  const raw = data.length ? data.join("\n") : text;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function openHttpSession(url, baseHeaders, controller) {
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
    ...baseHeaders,
  };
  const init = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-06-18",
        capabilities: {},
        clientInfo: { name: "mcp-smoke-test", version: "2.0" },
      },
    }),
    signal: controller.signal,
  });
  const sessionId = init.headers.get("mcp-session-id");
  await init.text();
  if (!sessionId) return { headers, sessionId: null };
  const withSession = { ...headers, "Mcp-Session-Id": sessionId };
  await fetch(url, {
    method: "POST",
    headers: withSession,
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
    signal: controller.signal,
  });
  return { headers: withSession, sessionId };
}

async function testHttpServer(name, config) {
  const url = config.url;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const { headers } = await openHttpSession(url, config.headers || {}, controller);
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" }),
      signal: controller.signal,
    });
    const text = await res.text();
    const payload = parseMcpPayload(text);
    const tools =
      payload?.result?.tools?.map((t) => t.name) ||
      [...text.matchAll(/"name"\s*:\s*"([^"]+)"/g)].map((m) => m[1]);
    return {
      name,
      status: tools.length ? "OK" : "FAIL",
      detail: tools.length
        ? `${tools.length} tools: ${tools.slice(0, 5).join(", ")}${tools.length > 5 ? "…" : ""}`
        : `HTTP ${res.status}: ${text.slice(0, 200)}`,
    };
  } catch (err) {
    return { name, status: "FAIL", detail: err.message.slice(0, 200) };
  } finally {
    clearTimeout(timer);
  }
}

function portOpen(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    const done = (value) => { try { socket.destroy(); } catch {} resolve(value); };
    socket.setTimeout(500);
    socket.on("connect", () => done(true));
    socket.on("error", () => done(false));
    socket.on("timeout", () => done(false));
  });
}

function testServer(name, config, baseEnv) {
  return new Promise((resolve) => {
    if (config.disabled) {
      resolve({ name, status: "SKIP", detail: "disabled in mcp.json" });
      return;
    }

    if (OUT_OF_SCOPE.has(name)) {
      resolve({ name, status: "SKIP", detail: "out of harness scope" });
      return;
    }

    if (PRESKIP.has(name)) {
      resolve({ name, status: "SKIP", detail: PRESKIP.get(name) });
      return;
    }

    const stype = config.type || "stdio";
    if (stype === "http" || stype === "sse" || stype === "remote" || config.url) {
      if (!config.command) {
        testHttpServer(name, config).then(resolve);
        return;
      }
    }

    if (!config.command) {
      resolve({ name, status: "FAIL", detail: "no command and no url" });
      return;
    }

    const command = interpolate(config.command, baseEnv);
    const args = (config.args || []).map((a) => interpolate(a, baseEnv));
    const env = { ...baseEnv };
    if (config.env) {
      for (const [k, v] of Object.entries(config.env)) {
        env[k] = interpolate(v, baseEnv);
      }
    }

    const child = spawn(command, args, { env, shell: true, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let sent = 0;
    // PHP stdio servers expect Content-Length framing; Node servers take
    // bare JSON lines. Detect from the server entrypoint.
    const framed = args.some((a) => a.endsWith("server.php")) || command.includes("server.php");

    // uvx/npx servers need longer cold start (package resolve).
    const slow = command.startsWith("uvx") || command.startsWith("npx") ||
      args.some((a) => a.includes("run-with-mcp-env") || a.includes("mysql-mcp-proxy"));
    const timeoutMs = slow ? 90000 : 25000;
    let done = false;
    const finish = (result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { child.stdin.end(); } catch {}
      try { child.kill("SIGKILL"); } catch {}
      resolve(result);
    };
    const timer = setTimeout(() => {
      const tools = extractTools(stdout);
      finish({
        name,
        status: tools.length ? "OK" : "TIMEOUT",
        detail: tools.length
          ? `${tools.length} tools: ${tools.slice(0, 5).join(", ")}${tools.length > 5 ? "…" : ""}`
          : (stderr || stdout).slice(0, 200),
      });
    }, timeoutMs);
    // Avoid waiting for the timeout when the answer already arrived:
    // as soon as tools/list response is seen, close stdin so well-behaved
    // servers exit, and finish on close.
    const earlyCheck = () => {
      if (done) return;
      if (extractTools(stdout).length && stdout.includes('"id":2')) {
        try { child.stdin.end(); } catch {}
        const t = setTimeout(() => finish({
          name,
          status: "OK",
          detail: `${extractTools(stdout).length} tools`,
        }), 3000);
        t.unref?.();
      }
    };

    const sendNext = () => {
      if (sent < messages.length) {
        const payload = framed ? frameMessage(messages[sent]) : JSON.stringify(messages[sent]) + "\n";
        child.stdin.write(payload);
        sent++;
        setTimeout(sendNext, 500);
      }
    };

    child.stdout.on("data", (d) => {
      stdout += d.toString();
      earlyCheck();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (err) => {
      finish({ name, status: "FAIL", detail: err.message });
    });
    child.on("close", (code) => {
      const tools = extractTools(stdout);
      finish({
        name,
        status: tools.length ? "OK" : code ? "FAIL" : "WARN",
        detail: tools.length
          ? `${tools.length} tools`
          : (stderr || stdout).slice(0, 250) || `exit ${code}`,
      });
    });

    sendNext();
  });
}

// Functional probes (Phase 2): a spawned process passing tools/list does NOT
// prove the server is usable from an agent session. Each entry calls one
// read-only tool and checks the response for a real payload. A server that
// answers tools/list but fails every functional probe is reported DEGRADED:
// green in Phase 1, red in practice (e.g. serena without project activation,
// codebase-memory-mcp without an indexed project).
// Probe args use ${workspaceFolder} interpolation like mcp.json.
const FUNCTIONAL_PROBES = {
  "codebase-memory-mcp": {
    calls: [{ tool: "list_projects", args: {} }],
    // Real payload must name this workspace root; the daemon may be alive
    // but serve only other projects. Project name in CBM is the path slug.
    check: (responses) => {
      const slug = workspace
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      const base = path.basename(workspace).toLowerCase();
      return responses.some((t) => {
        const low = t.toLowerCase();
        return low.includes(slug) || low.includes(base);
      })
        ? null
        : "list_projects answered but workspace project not listed";
    },
  },
  serena: {
    // Cold-spawn get_symbols_overview answers in ~3s once the server is up
    // and proves end-to-end usability incl. PHP LSP index. The fixture is
    // product-specific: on a migrated project the probe is SKIP, not DEGRADED.
    available: existsSync(path.join(workspace, "lib/Objects/Register/RegisterMVC.php")),
    skipDetail: "нет lib/Objects/Register/RegisterMVC.php: проверка serena не применима к этому проекту",
    calls: [
      {
        tool: "find_symbol",
        args: { name_path_pattern: "OrderService", relative_path: "lib/Objects/Order/OrderService.php", include_body: false },
      },
    ],
    check: (responses) =>
      responses.some((t) => t.includes("OrderService"))
        ? null
        : "find_symbol answered but OrderService not found (project not activated?)",
  },
  mysql: {
    calls: [{ tool: "list_tables", args: {} }],
    check: (responses) =>
      responses.some((t) => t.includes("Tables_in_") || t.includes("ct_"))
        ? null
        : "list_tables returned no table list",
  },
  git: {
    calls: [
      {
        tool: "git_status",
        args: { repo_path: "${workspaceFolder}" },
      },
    ],
    check: (responses) =>
      responses.some((t) => t.includes("branch") || t.includes("Branch"))
        ? null
        : "git_status answered but no branch info",
  },
  codegraph: {
    // Index is local and optional before `codegraph init`; probe a symbol that
    // exists in this product only when the index is present.
    available: existsSync(path.join(workspace, ".codegraph")),
    skipDetail: "нет .codegraph: функциональная проверка codegraph не применима",
    calls: [{ tool: "codegraph_explore", args: { query: "OrderService", maxFiles: 3 } }],
    check: (responses) =>
      responses.some((t) => t.includes("OrderService"))
        ? null
        : "codegraph_explore answered but OrderService not found (index missing?)",
  },
};

const PROBE_TIMEOUT_MS = 90000;

// Per-probe cold-start warmup: time after spawn before initialize is sent.
// Serena needs ~15s (uvx + LSP init) before it can answer tools/call;
// without this the probe races startup and times out under parallel load.
const PROBE_WARMUP_MS = { serena: 15000 };

function sendRpc(child, obj, framed) {
  const payload = framed ? frameMessage(obj) : JSON.stringify(obj) + "\n";
  child.stdin.write(payload);
}

// Reuses one spawned process per server: initialize once, then run each
// probe call sequentially and collect tools/call result texts.
function functionalProbe(name, config, baseEnv, probe) {
  return new Promise((resolve) => {
    const stype = config.type || "stdio";
    if (stype === "http" || stype === "sse" || stype === "remote" || (config.url && !config.command)) {
      probeHttpServer(name, config, probe).then(resolve);
      return;
    }
    if (!config.command) {
      resolve({ name, phase: 2, status: "SKIP", detail: "no command for functional probe" });
      return;
    }
    const command = interpolate(config.command, baseEnv);
    const rawArgs = (config.args || []).map((a) => interpolate(a, baseEnv));
    const args = rawArgs.map((a) => interpolateProbe(a, baseEnv));
    const env = { ...baseEnv };
    if (config.env) {
      for (const [k, v] of Object.entries(config.env)) {
        env[k] = interpolate(v, baseEnv);
      }
    }
    const child = spawn(command, args, { env, shell: true, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let done = false;
    const finish = (result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { child.stdin.end(); } catch {}
      try { child.kill("SIGKILL"); } catch {}
      resolve(result);
    };
    const timer = setTimeout(() => {
      finish({ name, phase: 2, status: "TIMEOUT", detail: `no functional answer in ${PROBE_TIMEOUT_MS / 1000}s` });
    }, PROBE_TIMEOUT_MS);
    const framed = args.some((a) => a.endsWith("server.php")) || command.includes("server.php");
    let nextId = 1;
    const resultTexts = [];
    const waitForId = (id, ms) =>
      new Promise((res) => {
        const t0 = Date.now();
        const poll = () => {
          const found = stdout.includes(`"id":${id}`);
          if (found || Date.now() - t0 > ms) res(found);
          else setTimeout(poll, 300);
        };
        poll();
      });
    child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.on("error", (err) => {
      finish({ name, phase: 2, status: "FAIL", detail: `spawn: ${err.message.slice(0, 150)}` });
    });
    (async () => {
      try {
        await new Promise((r) => setTimeout(r, PROBE_WARMUP_MS[name] || 3000));
        sendRpc(child, { jsonrpc: "2.0", id: nextId++, method: "initialize", params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "mcp-smoke-test", version: "2.0" } } }, framed);
        await new Promise((r) => setTimeout(r, 1500));
        sendRpc(child, { jsonrpc: "2.0", method: "notifications/initialized" }, framed);
        for (const call of probe.calls) {
          const id = nextId++;
          const callArgs = JSON.parse(JSON.stringify(call.args || {}), (k, v) =>
            typeof v === "string" ? interpolateProbe(v, baseEnv) : v);
          sendRpc(child, { jsonrpc: "2.0", id, method: "tools/call", params: { name: call.tool, arguments: callArgs } }, framed);
          const answered = await waitForId(id, PROBE_TIMEOUT_MS - 10000);
          if (!answered || done) {
            finish({ name, phase: 2, status: "TIMEOUT", detail: `tools/call ${call.tool}: no answer` });
            return;
          }
        }
        await new Promise((r) => setTimeout(r, 2000));
        // Collect tools/call result texts line by line: responses may span
        // multiple lines (e.g. mysql list_tables returns a long JSON array),
        // so regex over the raw stream is unreliable. Parse each JSON-RPC
        // line and extract content[].text.
        const texts = [];
        for (const line of stdout.split(/\r?\n/)) {
          const t = line.trim();
          if (!t.startsWith("{")) continue;
          try {
            const msg = JSON.parse(t);
            const content = msg?.result?.content;
            if (Array.isArray(content)) {
              for (const item of content) {
                if (typeof item?.text === "string") texts.push(item.text.slice(0, 4000));
              }
            }
          } catch {}
        }
        const fail = probe.check(texts);
        finish(fail
          ? { name, phase: 2, status: "DEGRADED", detail: fail.slice(0, 200) }
          : { name, phase: 2, status: "OK", detail: `functional: ${probe.calls.map((c) => c.tool).join(",")}` });
      } catch (err) {
        finish({ name, phase: 2, status: "FAIL", detail: String(err?.message || err).slice(0, 150) });
      }
    })();
  });
}

function interpolateProbe(value, env) {
  return interpolate(value, { ...env, workspaceFolder: workspace });
}

async function probeHttpServer(name, config, probe) {
  const url = config.url;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const { headers } = await openHttpSession(url, config.headers || {}, controller);
    const texts = [];
    let id = 10;
    for (const call of probe.calls) {
      const callArgs = JSON.parse(JSON.stringify(call.args || {}), (k, v) =>
        typeof v === "string" ? interpolateProbe(v, {}) : v);
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: id++,
          method: "tools/call",
          params: { name: call.tool, arguments: callArgs },
        }),
        signal: controller.signal,
      });
      const text = await res.text();
      const payload = parseMcpPayload(text);
      const content = payload?.result?.content?.map((c) => c.text ?? "").join("\n");
      texts.push((content || text).slice(0, 2000));
    }
    const fail = probe.check(texts);
    return fail
      ? { name, phase: 2, status: "DEGRADED", detail: fail.slice(0, 200) }
      : { name, phase: 2, status: "OK", detail: `functional: ${probe.calls.map((c) => c.tool).join(",")}` };
  } catch (err) {
    return { name, phase: 2, status: "FAIL", detail: err.message.slice(0, 200) };
  } finally {
    clearTimeout(timer);
  }
}

const cfg = JSON.parse(readFileSync(mcpJsonPath, "utf8"));
const baseEnv = loadEnvFile();
const PRESKIP = new Map();
if (await portOpen(3306)) {
  PRESKIP.set("mysql", "relay 3306 already active; mysql MCP is stdio per client");
}
const onlyFilter = process.argv.slice(2).find((a) => a.startsWith("--only="))?.slice(7).split(",").filter(Boolean);
console.log(`Workspace: ${workspace}`);
console.log(`MYSQL_DATABASE: ${baseEnv.MYSQL_DATABASE || "(empty)"}\n`);

// Parallel probes: sequential runs summed every per-server timeout
// (uvx/npx cold start up to 90s each), which looked like a hang.
// Concurrency keeps total time near the slowest single probe.
const CONCURRENCY = 5;
const entries = Object.entries(cfg.mcpServers).filter(([name]) => !onlyFilter || onlyFilter.includes(name));
const results = new Array(entries.length);
let cursor = 0;
async function worker() {
  for (;;) {
    const i = cursor++;
    if (i >= entries.length) return;
    const [name, config] = entries[i];
    try {
      results[i] = await testServer(name, config, baseEnv);
    } catch (err) {
      results[i] = { name, status: "FAIL", detail: String(err?.message || err).slice(0, 200) };
    }
    const r = results[i];
    console.log(`${r.status.padEnd(7)} ${name} — ${r.detail}`);
  }
}
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, entries.length) }, () => worker()));

console.log("\n=== Phase 1: process spawn (tools/list) ===");
let failed = 0;
for (const r of results) {
  console.log(`${r.status.padEnd(7)} ${r.name}`);
  if (r.status === "FAIL" || r.status === "TIMEOUT") failed++;
}

// Phase 2: functional probes. Only servers that passed Phase 1 AND have a
// probe defined are re-probed with a real tools/call. A server answering
// tools/list but failing its probe is DEGRADED, not OK.
const skipPhase2 = process.argv.includes("--no-functional");
const phase2 = [];
if (!skipPhase2) {
  console.log("\n=== Phase 2: functional probes (tools/call) ===");
  const phase1ok = entries
    .map(([name, config], i) => ({ name, config, r: results[i] }))
    .filter(({ name, r }) => r.status === "OK" && FUNCTIONAL_PROBES[name] && (!onlyFilter || onlyFilter.includes(name)));
  const F2_CONCURRENCY = 2;
  let f2cursor = 0;
  async function f2worker() {
    for (;;) {
      const i = f2cursor++;
      if (i >= phase1ok.length) return;
      const { name, config } = phase1ok[i];
      const probe = FUNCTIONAL_PROBES[name];
      if (probe && probe.available === false) {
        const pr = { name, phase: 2, status: "SKIP", detail: probe.skipDetail || "probe fixture not present in workspace" };
        phase2.push(pr);
        console.log(`${pr.status.padEnd(7)} ${pr.name} — ${pr.detail}`);
        continue;
      }
      try {
        const pr = await functionalProbe(name, config, baseEnv, probe);
        phase2.push(pr);
      } catch (err) {
        phase2.push({ name, phase: 2, status: "FAIL", detail: String(err?.message || err).slice(0, 150) });
      }
      const pr = phase2[phase2.length - 1];
      console.log(`${pr.status.padEnd(7)} ${pr.name} — ${pr.detail}`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(F2_CONCURRENCY, phase1ok.length) }, () => f2worker()));
}

console.log("\n=== Summary ===");
for (const r of results) {
  const f2 = phase2.find((p) => p.name === r.name);
  const shown = f2 && f2.status !== "OK" ? `${r.status}→${f2.status}` : r.status;
  console.log(`${shown.padEnd(12)} ${r.name}${f2 && f2.status !== "OK" ? ` — ${f2.detail}` : ""}`);
  if ((f2 && (f2.status === "FAIL" || f2.status === "TIMEOUT" || f2.status === "DEGRADED")) ||
      (!f2 && (r.status === "FAIL" || r.status === "TIMEOUT"))) failed++;
}
process.exit(failed ? 1 : 0);
