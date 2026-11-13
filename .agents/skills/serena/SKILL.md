---
name: serena
description: "Inspect PHP symbols, references and diagnostics with Serena MCP before scoped source edits. Use for find_symbol, symbol bodies, references and PHP LSP checks."
---

# Serena MCP

Use Serena after codebase-memory-mcp and codegraph to confirm symbols and their
references. Symbol operations require an active language server for that language.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/serena.mdc),
   [editing rule](../../../.cursor/rules/code-editing.mdc) and
   [server document](docs/mcp/serena.md) for supported tools and backend history.
2. Call `initial_instructions` before coding. Verify the active project/root
   belongs to the current workspace; use its configured project-specific server.
3. For PHP, call `find_symbol` with `depth: 1` for the class, then
   `include_body: true` for the method and `find_referencing_symbols` for callers.
   Read the entire affected file before editing.
4. Plan the smallest authorized edit. A planning-only request does not authorize
   source edits, even if `replace_content` is auto-approved by the client.
   Follow the host's editing-tool requirements first. Otherwise prefer
   `replace_symbol_body` for PHP with verified LSP ranges, `replace_content` for
   unique text anchors, and line-based tools only when symbol ranges are invalid.
   Tool permission is not task authorization; do not alter permission settings.
5. For renaming, preview `replace_in_files` with `dry_run` and apply only reviewed
   `occurrence_ids`. Find implementations with scoped `search_for_pattern`.
6. Inspect the changed source, `git diff` and `get_diagnostics_for_file`; rerun
   references for public symbols and execute the relevant project tests.

## Isolation And Safety

- Use only the current project's server and relative source paths. Do not start
  a second stdio server or switch to another repository's language server.
- PHP has Intelephense support here. JS, Vue and TPL require file operations;
  do not interpret failed symbol extraction as absence of code.
- Free Intelephense does not support `rename_symbol` or `find_implementations`.
- Documentation discovery uses jdocmunch; do not scan the entire `.doc` tree.
- Preview bulk edits, preserve unrelated changes and obtain required permissions.
  After a client timeout, reread the file before retrying a mutating operation.
- Report unavailable diagnostics explicitly; they do not replace tests or PHPStan.

## History

- 2026-11-10: separated edit authorization from client auto-approval and specified the editing-tool fallback order.
