# CodePrism integrations

Condensed from the upstream `references/INTEGRATIONS.md` for this project.

## Install

Python 3.12 or newer is required. The project keeps a local virtual
environment so the package version is pinned and does not leak into the system.

```
uv venv .cursor/tools/codeprism-ai/venv
uv pip install --python .cursor/tools/codeprism-ai/venv/bin/python codeprism-ai==0.1.11
```

The user service runs `.agents/skills/codeprism/scripts/codeprism_serve.py` from this virtual
environment. The launcher `.agents/skills/codeprism/scripts/codeprism-mcp.sh` is a client bridge.

## Client configuration

The MCP record is `codeprism` and lives in the project canon. Client files are
generated from it and must not be edited by hand.

```
codeprism: Streamable HTTP, http://127.0.0.1:9201/mcp
```

The user service starts one server per project. Stdio clients use
`.agents/skills/codeprism/scripts/codeprism-mcp.sh` as a bridge to the canonical HTTP endpoint.
The bridge requires `uvx` and an offline-available `mcp-proxy`; it does not start
the server. Its optional `CODEPRISM_TARGET` must resolve to the bridge's project
root. The server selects its project from the positional argument passed at
startup. Set `CODEPRISM_NO_AUTO_INDEX=1` in the server environment to disable
the background index and its watcher.

## Project config

`.codeprism.toml` in the project root controls the index and the security scan.
The file is local to the machine and is listed in `.git/info/exclude`, so it is
not committed. Recreate it on a new machine from the block below.

```
[codeprism]
languages = ["php", "javascript", "typescript"]
respect_gitignore = true
auto_index = true
enable_embeddings = false
enable_security_gate = true
watch_debounce_ms = 800

[codeprism.security]
block_on_secrets = true
warn_on_weak_crypto = true
check_new_dependencies = true
ignore_paths = [
  "*/vendor/*",
  "*/node_modules/*",
  "*/templates_c/*",
  "*/frontend/dist/*",
  "*/scripts/plugins/*",
  "*/scripts/jscalendar-1.0/*",
  "*/scripts/ui/minified/*",
  "*/scripts/ui/i18n/*",
  "*/resources/lang/*",
  "*/sql/migrations/*",
  "*/tests/fixtures/*",
  "*/*.min.js",
]
```

`[codeprism.security].ignore_paths` is applied twice: it removes files from the
index and from security scans. In this project it excludes `vendor`,
`node_modules`, `templates_c`, `frontend/dist`, third-party `scripts/plugins`,
`jscalendar`, minified and i18n bundles, `resources/lang`, `sql/migrations`,
test fixtures and `*.min.js`.

The server loads this file at startup. The CLI `codeprism index` and the MCP
tool `index_project` build their config from flags and ignore the file, so they
bring excluded files back. `index_project` is disabled on the shared HTTP server.
To apply a config change, restart the server: it
rebuilds incrementally and removes the excluded files. For one file use
`update_file`.

## Build the index

The server builds the index itself on start, because `auto_index` is true. A
restart is the normal rebuild and applies the project config.

For a clean rebuild, stop the server, delete the SQLite file in the user-data
directory, then start the server again. A full build of this repository takes
about 15 seconds and yields about 1930 files, 13500 symbols and 22800 edges.
Incremental runs take about 4 seconds.

Do not use `codeprism index .` for a normal refresh: the CLI ignores
`.codeprism.toml` and would index the excluded third-party files again.

The index is stored in the platform user-data directory, one SQLite file per
project. It is not part of the repository and is not migrated with it.

## Live updates

The user service starts `.agents/skills/codeprism/scripts/codeprism_serve.py`, not `codeprism serve`
directly. With background indexing enabled, the wrapper runs the MCP server and,
after the first index, starts
the watchdog-based file watcher inside the server process. The watcher uses the
same graph and storage, so a saved file is normally visible after 1-2 seconds.
With `CODEPRISM_NO_AUTO_INDEX=1`, the background index and watcher do not start.

Watched extensions are the indexed languages. The watcher skips `vendor`,
`node_modules`, `templates_c`, `dist`, `plugins`, `jscalendar-1.0`, `minified`,
`i18n`, `lang`, `migrations`, `fixtures` and `*.min.js`. Deleted files are
removed from the graph.

The separate `codeprism watch .` command is not used: it ignores
`.codeprism.toml` and watches every directory. The `index_project` tool is not
used either, for the same reason. A `.codeprism.toml` change needs a restart.

## Embeddings

Embeddings stay disabled. Enabling them in 0.1.11 fails on this project with
`DuplicateIDError: Expected IDs to be unique, found 170 duplicated IDs`, and the
vector store stays empty. Even when it works, `search_symbol` switches from
substring matching to semantic-only search, which can miss an exact class name.

If a later version fixes the duplicate IDs, compact models to consider:

| Model | Size | Use |
|---|---|---|
| `all-MiniLM-L6-v2` | about 90 MB | English identifiers, smallest |
| `BAAI/bge-small-en-v1.5` | about 130 MB | English, better retrieval |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | about 470 MB | English plus Russian comments |

The extras add about 800 MB before the model download.

## Verify

```
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=codeprism
```

Expected for the current HTTP server: `OK codeprism` and 20 tools. The HTTP
server omits `index_project` from `tools/list`.

Ask for `get_graph_stats` and check the file and symbol counts.

## Multi-project

Each project has one HTTP server process and its own port. Clients share the
project server. The server selects its project at startup, not per request.

Each project keeps its own SQLite index in the user-data directory, so two
projects never share or overwrite a graph.

The transfer of CodePrism to another project is still under investigation;
automatic migration is not established. The existing unit generator requires the
target project to contain its own `.cursor/tools/codeprism-ai/venv/bin/python`
and `.agents/skills/codeprism/scripts/codeprism_serve.py`. It prepares a unit in an existing
output directory, but does not install or start the unit:

```
python3 .cursor/mcp-stack/add-codeprism.py <project> <port> --output-dir <unit-dir>
```

Review and install the generated unit, then reload and enable it using the
commands printed by the generator. Configure the same port in the target
project's canonical MCP record. Stop any old stdio server for that project before
starting HTTP: the old process does not participate in the HTTP lock.

## Troubleshooting

- Tools are missing: check the MCP record and restart the client.
- `index not ready`: wait for the background refresh.
- `ambiguous path`: pass more of the path, for example
  `lib/Objects/Order/Order.php` instead of `Order.php`.
- `file not indexed`: the file may be git-ignored or use an unsupported
  language. Smarty `.tpl` and Markdown are not indexed.
- Stale graph after edits: call `update_file` for one file or restart the server.
- Security scan blocks a test fixture: move secrets out of fixtures or exclude
  the path in the project configuration.
- Python virtual environment missing after a move: recreate it with the install
  commands above, the package is not committed.

## Removing

Stop and disable the project's user service before removing its environment.
Remove the MCP record from the canon, delete `.cursor/tools/codeprism-ai` and
regenerate client views. The user-data index can be deleted separately; it is
rebuilt on the next start when background indexing is enabled.
