#!/usr/bin/env node

import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

function findProjectRoot(start) {
  let dir = start;
  for (;;) {
    if (fs.existsSync(path.join(dir, ".cursor")) || fs.existsSync(path.join(dir, ".git"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      throw new Error("mysql-mcp-proxy: project root not found");
    }
    dir = parent;
  }
}

const projectRoot =
  process.env.MCP_WORKSPACE ||
  findProjectRoot(path.dirname(fileURLToPath(import.meta.url)));
const targetHost = process.env.MYSQL_HOST || "127.0.0.1";
const targetPort = Number(process.env.MYSQL_PORT || "8031");
const listenHost = process.env.MYSQL_MCP_LISTEN_HOST || "127.0.0.1";
// The upstream MCP accepts host but not port in connect_db. Keep its local
// relay on the standard MySQL port and forward to Docker's published port.
const listenPort = Number(process.env.MYSQL_MCP_LISTEN_PORT || "3306");

const connectionDefaults = {
  host: listenHost,
  user: process.env.MYSQL_USER || "",
  password: process.env.MYSQL_PASSWORD || "",
  database: process.env.MYSQL_DATABASE || "",
};

if (!connectionDefaults.user || !connectionDefaults.database) {
  console.error("mysql-mcp-proxy: MYSQL_USER and MYSQL_DATABASE are required");
  process.exit(2);
}

const relay = net.createServer((client) => {
  const upstream = net.createConnection({ host: targetHost, port: targetPort });
  client.pipe(upstream);
  upstream.pipe(client);
  const close = () => {
    client.destroy();
    upstream.destroy();
  };
  client.on("error", close);
  upstream.on("error", (error) => {
    console.error(`mysql-mcp-proxy: database relay error: ${error.message}`);
    close();
  });
  client.on("close", () => upstream.destroy());
  upstream.on("close", () => client.destroy());
});

const child = spawn("npx", ["-y", "@f4ww4z/mcp-mysql-server"], {
  cwd: projectRoot,
  env: process.env,
  stdio: ["pipe", "pipe", "pipe"],
});

const pending = new Map();
let nextInternalId = 900000;
let connected = false;
const waitingForConnection = [];

function sendToChild(message) {
  child.stdin.write(`${JSON.stringify(message)}\n`);
}

function sendError(id, message) {
  process.stdout.write(`${JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code: -32603, message },
  })}\n`);
}

function connectionArguments(argumentsObject = {}) {
  return {
    ...connectionDefaults,
    ...argumentsObject,
    // The upstream MCP has no port field. The relay exposes the configured
    // Docker port on the local standard MySQL port to the upstream process.
    host: listenHost,
  };
}

function startConnection(originalRequest) {
  const internalId = nextInternalId++;
  pending.set(internalId, { type: "auto-connect", originalRequest });
  sendToChild({
    jsonrpc: "2.0",
    id: internalId,
    method: "tools/call",
    params: {
      name: "connect_db",
      arguments: connectionArguments(),
    },
  });
}

function handleParentMessage(message) {
  if (message.method !== "tools/call") {
    if (message.id !== undefined) pending.set(message.id, { type: "passthrough" });
    sendToChild(message);
    return;
  }

  const name = message.params?.name;
  if (name === "connect_db") {
    pending.set(message.id, { type: "connect", originalRequest: message });
    sendToChild({
      ...message,
      params: {
        ...message.params,
        arguments: connectionArguments(message.params.arguments),
      },
    });
    return;
  }

  const databaseTools = new Set(["list_tables", "describe_table", "query", "execute"]);
  if (databaseTools.has(name) && !connected) {
    waitingForConnection.push(message);
    if (waitingForConnection.length === 1) startConnection(message);
    return;
  }

  pending.set(message.id, { type: "passthrough" });
  sendToChild(message);
}

const childLines = readline.createInterface({ input: child.stdout });
childLines.on("line", (line) => {
  if (!line.trim()) return;
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    console.error(`mysql-mcp-proxy: ignored non-JSON child output: ${line}`);
    return;
  }

  const pendingRequest = pending.get(message.id);
  if (pendingRequest?.type === "auto-connect") {
    pending.delete(message.id);
    const ok = !message.error && !message.result?.isError;
    connected = ok;
    const queued = waitingForConnection.splice(0);
    if (!ok) {
      for (const request of queued) {
        sendError(request.id, "MySQL auto-connect failed. Check .codex/mcp.env and Docker MySQL port.");
      }
      return;
    }
    for (const request of queued) {
      pending.set(request.id, { type: "passthrough" });
      sendToChild(request);
    }
    return;
  }

  if (pendingRequest?.type === "connect") {
    pending.delete(message.id);
    connected = !message.error && !message.result?.isError;
  } else if (message.id !== undefined) {
    pending.delete(message.id);
  }
  process.stdout.write(`${JSON.stringify(message)}\n`);
});

child.stderr.on("data", (chunk) => process.stderr.write(chunk));
child.on("exit", (code, signal) => {
  relay.close();
  process.exit(code ?? (signal ? 1 : 0));
});

relay.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`mysql-mcp-proxy: port ${listenPort} is already in use, assuming relay is already active`);
  } else {
    console.error(`mysql-mcp-proxy: relay server error: ${error.message}`);
  }
});

relay.listen(listenPort, listenHost, () => {
  console.error(`mysql-mcp-proxy: relay ${listenHost}:${listenPort} -> ${targetHost}:${targetPort}`);
});

const parentLines = readline.createInterface({ input: process.stdin });
parentLines.on("line", (line) => {
  if (!line.trim()) return;
  try {
    handleParentMessage(JSON.parse(line));
  } catch (error) {
    console.error(`mysql-mcp-proxy: invalid parent message: ${error.message}`);
  }
});

function shutdown() {
  relay.close();
  child.kill();
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
