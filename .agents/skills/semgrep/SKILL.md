---
name: semgrep
description: "Scan scoped workspace files for security risks with Semgrep MCP. Use for SQL, XSS, access-control and user-data changes, custom rules and AST inspection."
---

# Semgrep MCP

Use a local scoped scan for security-sensitive changes. Semgrep findings require
review and do not replace type analysis or behavior tests.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/semgrep.mdc) and
   [server document](docs/mcp/semgrep.md) for tool arguments and installation.
2. Select the relevant changed files and resolve absolute paths inside the
   current workspace. Exclude unrelated repositories and secret files.
3. Call `semgrep_scan` with the narrow `code_files` list. For a custom check,
   inspect `semgrep_rule_schema` and use `semgrep_scan_with_custom_rule` with YAML.
4. Use `get_supported_languages` or `get_abstract_syntax_tree` only when language
   support or a match needs investigation.
5. Review findings against the current source, trust boundary and callers.
   Distinguish confirmed defects, false positives and incomplete scan coverage.
6. Report file/line, rule, risk and validation outcome. Run the appropriate type
   checker and tests separately; an empty scan does not prove complete security.

## Isolation And Safety

- Pass only absolute paths within the current repository. Keep scans local unless
  the user explicitly authorizes transmitting code to an external service.
- `semgrep_findings` reads past platform results and needs a token; it is not a
  replacement for a local scan of current source.
- Do not expose tokens or account details in output. Do not run remote or
  supply-chain scans as an implicit expansion of a file-scanning request.
- Do not auto-fix code, broaden rules or install dependencies to hide a finding.
  Report unavailable tools, unsupported languages and scan errors as limitations.
