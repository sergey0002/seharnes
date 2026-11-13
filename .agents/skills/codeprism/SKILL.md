---
name: codeprism
description: Uses the CodePrism knowledge graph to give an agent structural context before reading files: symbols, callers, callees, impact, dependencies, data flow and a security gate before writes. Use when exploring an unfamiliar module, planning a refactor, tracing callers, checking blast radius, or scanning proposed code for secrets and vulnerabilities before writing.
license: MIT
compatibility: Requires the codeprism-ai package (0.1.11) and the codeprism MCP server configured in the project. Works in Cursor, Codex, Kilo and any MCP client.
metadata:
  version: "0.1.11"
  author: knight22-21
  repository: https://github.com/knight22-21/CodePrism
  category: code-quality-review
---

# CodePrism Knowledge Graph

CodePrism keeps a persistent knowledge graph of the project: every file, symbol,
import, call and data-flow edge. Query the graph first and read source files only
when the graph is not enough. On large codebases this cuts context by 60 to 80
percent. The tool names below are verified against the installed server.

## Когда применять

Use this skill when:

- the task asks how code is structured or what a module does;
- you need callers, callees, dependents or blast radius before a change;
- you plan a refactor and must know what breaks and which tests are affected;
- you need a security check before writing code;
- you trace data flow or dependencies between files;
- the repository is large and reading whole files is expensive;
- the user says "graph", "context", "impact", "callers", "callees".

Do not use it when:

- you need the exact implementation body, the graph gives structure only;
- the task touches documentation, Smarty templates or Markdown, they are not indexed;
- the change is tiny and a direct read is cheaper.

## Вход

- `file`: path relative to the project root, for example `lib/Objects/Order.php`.
- `symbol`: class, method or function name inside that file.
- `depth`: graph distance, 2 is the default and covers callers and callees.
- `session_id`: any stable id for the current task, used by session tools.
- `original` and `proposed`: file contents for `scan_diff`.

If a path is ambiguous, use the longer path. Ambiguous names return an error that
asks for more of the path.

## Шаги

1. Check that the index is ready.

   Call `get_graph_stats` with `path="."`. A ready graph returns file, symbol and
   edge counts. If the status is indexing, wait or continue with `codegraph`.
   Always pass `path`; the schema marks it optional, but the server expects it.

2. Get structural context before reading a file.

   Call `get_context` with `file`, `symbol`, `depth=2`. The answer contains the
   signature, callers, callees and types, usually under 400 tokens.

3. Widen only as needed.

   | Question | Tool |
   |---|---|
   | Who calls this function? | `get_callers(file, function)` |
   | What does this function call? | `get_callees(file, function)` |
   | What breaks if I change it? | `get_impact(file, symbol)` |
   | What does this file import? | `get_dependencies(file)` |
   | Which files depend on this one? | `get_dependents(file)` |
   | How does a value move? | `get_data_flow(file, symbol)` |
   | Where is the symbol? | `search_symbol(query, kind)` |
   | What is this file for? | `get_module_summary(file)` |
   | What is in this directory? | `get_file_map(project_path)` |

4. Run the security gate before any write.

   For a new file or a full file call `scan_file(file, content)`. For an edit call
   `scan_diff(original, proposed, file)`. A `BLOCK` status means a critical issue:
   do not write, explain the issues. A `WARN` status means write only after
   reporting the warning.

5. Track session state on long tasks.

   `record_read(session_id, file, symbol)` marks context already fetched.
   `record_write(session_id, file, content_before, content_after)` records a
   write. `get_session_context(session_id)` returns a compact digest.
   `undo_write(session_id, steps)` rolls agent-authored writes back.

6. Read the file only when the graph is not enough. Then edit it.

7. With background indexing enabled, the server wrapper starts a file watcher
   after the initial index is ready. Its 800 ms debounce normally makes saved
   files visible after 1-2 seconds. `CODEPRISM_NO_AUTO_INDEX=1` disables the
   background index and watcher. Use `update_file(path)` for an immediate update.
   Restart the server to apply `.codeprism.toml` changes. `index_project` is
   disabled on the shared HTTP server because it ignores the project config.

### Workflow: understand a function

1. `search_symbol(query="processPayment", kind="function")`.
2. `get_context(file, symbol, depth=2)`.
3. If the body is needed, read only that file.
4. `record_read` with the task session id.

### Workflow: refactor safely

1. `get_impact(file, symbol)` for blast radius and affected tests.
2. `get_callers` and `get_callees` for direct relations.
3. Prepare proposed content without writing it.
4. Run `scan_diff` for every proposed file change.
5. Write only when the status is not `BLOCK`; report a `WARN` first.
6. `record_write` after the write.

### Workflow: security check

```
original = content before the edit
proposed = content after the edit
result = scan_diff(original, proposed, file)
if result.status == "BLOCK": do not write
else: report WARN if present, then write and record_write
```

Additional checks: `check_secret_exposure(content)` for secrets and
`check_dependencies_cve(requirements)` for dependency CVEs.

## Выход

- A compact structural answer: signature, relationships, files and line numbers.
- For impact: severity, dependents, affected tests.
- For security: status `PASS`, `WARN` or `BLOCK` plus the issue list.
- For sessions: a digest of reads and writes plus a rollback option.

## Ограничения

- The graph gives structure, not full implementations. Read the file for the body.
- Calls are linked through imports for Python only. In other languages they are
  linked by name, so a common name can link to the wrong function.
- PHP is supported: namespaces, classes, traits, interfaces and methods.
- Smarty `.tpl`, Markdown and other non-code files are not indexed.
- The index honors `.gitignore`. Ignored files are absent from graph queries;
  tools that accept content directly can still scan supplied content.
- The index lives in the platform user-data directory, one SQLite file per
  project. It is not stored in the repository.
- With background indexing enabled, the watcher starts after the initial index
  and updates indexed editor changes. Disabling auto-index also disables it.
- If the graph is not ready, fall back to `codegraph` for source and relations
  and to a direct read.
- `PASS` means no known detector matched. It is not proof that the code is safe.
  Patterns are heuristic: an AWS access key is blocked, an arbitrary fake `sk-`
  string may pass.
- The index scope comes from `.codeprism.toml` in the project root. This project
  indexes PHP, JavaScript and TypeScript and skips third-party plugins,
  translations, fixtures and Doctrine migrations. The CLI `index` and the
  `index_project` tool ignore that file, so a restart is the safe refresh.
- The watcher updates the index on save with a 1-2 second delay. Excluded directories and
  `*.min.js` files are not watched. The separate `watch` command and the
  `index_project` tool are not used because they ignore the project config.
- Embeddings are disabled. In version 0.1.11 the build fails with a duplicate
  symbol ID error, and enabling them replaces substring symbol search with
  semantic-only search.

## Tool reference

The shared HTTP server selects one project at startup; `project_path` does not
switch its graph. `get_graph_stats` expects `path`; pass `path="."` for the
current project. HTTP `tools/list` exposes 20 tools; `index_project` is disabled.

| Tool | Required arguments | Optional arguments |
|---|---|---|
| `update_file` | `path` | - |
| `get_graph_stats` | - | `path` |
| `get_context` | `file`, `symbol` | `depth` |
| `get_module_summary` | `file` | - |
| `get_file_map` | - | `project_path` |
| `get_impact` | `file`, `symbol` | - |
| `get_callers` | `file`, `function` | - |
| `get_callees` | `file`, `function` | - |
| `get_data_flow` | `file`, `symbol` | - |
| `search_symbol` | `query` | `project_path`, `kind` |
| `get_dependencies` | `file` | - |
| `get_dependents` | `file` | - |
| `scan_file` | `file` | `content` |
| `scan_diff` | `original`, `proposed` | `file` |
| `check_secret_exposure` | `content` | - |
| `check_dependencies_cve` | `requirements` | - |
| `record_read` | `session_id`, `file`, `symbol` | - |
| `record_write` | `session_id`, `file`, `content_before`, `content_after` | - |
| `get_session_context` | `session_id` | - |
| `undo_write` | `session_id` | `steps` |

Setup, per-client configuration and troubleshooting:
[integrations](references/integrations.md).
