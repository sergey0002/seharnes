# Serena MCP

Inspects PHP symbols, references and language-server diagnostics.
Code graphs provide structural context before symbol-level investigation.

The workflow reads class members, method bodies and callers before an edit.
Bulk replacements receive a dry-run preview before selected matches are applied.
Source inspection, diagnostics and tests verify the resulting change.
Client auto-approval never expands task scope: planning does not permit source edits.
The host editing policy takes precedence over the tool fallback order.

The configured server belongs to one project and is not shared across roots.
JS, Vue and TPL use file operations because their language servers are absent.
The bundled server document preserves backend comparisons and incident history.
