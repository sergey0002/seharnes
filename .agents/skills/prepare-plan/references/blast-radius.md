## Step P1 — Blast radius: mandatory tool ladder and risk classification

Breaking **other** features/tasks with a "small" change is the single most common
failure of this skill. This step exists to make that failure structurally hard, not
to rely on judgment. Any "Before" / as-is / root cause line comes only from **Read**
of a whole file after a tool points to it. A tool snippet is never the final Before.

Check `MCP_CONFIG` / IDE for which servers are green. Concrete tool → server binding
for this repo lives in `ADAPTERS.local.md` (`BLAST_RADIUS_LADDER`); this section is
the portable **order and gate logic**.

Resolve Tier 0 methods, arguments, paging and freshness from CODE_GRAPH_RULES
in ADAPTERS before the first call. Never freeze method counts in this portable
core. A failed argument-validation call is not evidence of a red tier.

### P1.1 — The ladder (fixed order, do not skip a green tier)

Batch independent searches according to the host tool rules. Documentation uses
the installed documentation search adapter first; literal/file searches and Git
commands use the host's batching mechanism.

A tool-registry search (the `execute` tool in Cursor, `list_mcp_resources` plus
adapter listing in other environments) is **not** a code graph: it finds MCP tool
paths by name/description. A `namespace` filter keeps only tools of that MCP
server; an unknown or unregistered namespace yields `items: []` with no error.
Empty result therefore means "no such tool", never "no callers". Never record
Tier 0-3 as done from an empty registry-search result alone — either drop the `namespace` filter and retry, or call the MCP
server tool directly, or compensate with Grep + whole-file Read.

A tier being unnecessary for this specific change (e.g. no DB touched) is a valid
reason to skip it — **an unavailable/red tool is not**. Red tier → compensate with
Grep + whole-file Read and record "tier N red, compensated" in the plan.

```
Tier 0  Graph/dependency tool   → indexed callers/callees of the exact symbol/route/table
        (architecture-level "who depends on this" — the primary map)
Tier 0b Module/impact tool      → module summary, impact of the edit and data flow for
        PHP, JS and TS (codeprism in this repo); structural answer without reading a file.
        It does not replace the whole-file Read and does not index Smarty or Markdown
Tier 1  Real call-graph tool    → language-specific static call graph (PHP: real call graph,
        not name-matching) — required whenever a method signature or shared class changes;
        catches interface/DI-indirect callers the generic graph may miss
Tier 2  Symbol/LSP tool         → exact definition + all references, including interface
        implementations — required before renaming or changing any public symbol
Tier 3  Full-text/semantic search → non-graph usages: template includes, front-end
        bindings, string-based calls, copy-pasted clones — required for any change that
        touches a template/script/shared helper, and always for rename
Tier 4  Git history (git-task-blame skill) → who else, in which task, already touched
        this exact range, and why — required before plan handoff and again on re-audit,
        regardless of tiers 0-3 (see P0.5b)
Tier 5  DB schema tool          → only if the change touches columns/tables — FK,
        triggers, other consumers of the same table
Tier 6  Pattern/security scanner → same vulnerable or duplicated pattern elsewhere —
        required before any auth/SQL/payment/PII-adjacent change
Tier 7  Type/static analysis    → type-level fallout on touched files **and** the
        callers found in tiers 0-3 — required after any signature/type change
Tier 8  Runtime/browser tool    → last resort, only when static Read cannot explain
        the symptom (e.g. Vue reactivity, race condition)
```

Record in the plan which tier found which caller — do not collapse tiers into one
generic "MCP found X"; a reviewer (including a weak-model reviewer) must be able to
tell which tool is responsible for which claim.

### P1.2 — Risk classification (required per changed symbol/file)

Classify every symbol/file in Patches **before** writing Options (P4). This drives
how much of the ladder is mandatory and how strict P2.8/P2.9 are.

| Signal (any one present raises the level) | Level |
|---|---|
| Single caller, not shared, no DB/money/auth touch, has test coverage | Low |
| 2+ callers across the **same** feature, or touches a template used only there | Medium |
| Shared across **2+ features/screens/jobs** (P2.8 applies), or touches DB columns | High |
| Touches money/auth/data-mutation, or git-task-blame (Tier 4) finds **3+ prior tasks** on this exact range ("hot spot"), or a related task's branch is still open on origin | Critical |

```
□ Critical/High → full ladder (Tier 0-4 mandatory, 5-7 if applicable) + IN/OUT table (P2.8)
□ Medium → Tier 0, 2, 3 mandatory; Tier 4 for every file with history per P0.5b
□ Low → Tier 0 + 2 still mandatory; Tier 4 for existing history; other tiers as applicable
□ Record the level and the reason in the plan next to each Patches file
```

A "hot spot" (Critical via git-task-blame) means the code has broken before or is
fragile by nature — treat every touch to it as a regression risk, not just a feature
add.

### P1.3 — Blast radius procedure (required before P5)

```
1. Tier 0 (+ Tier 1 for PHP signature/class changes) → callers and callees
2. Tier 2 → confirm no missed reference (interfaces, DI, dynamic calls)
3. Tier 3 → non-graph usages (templates, front-end, clones)
4. Tier 4 (git-task-blame) → prior tasks on the exact range (all existing-history patch files)
5. Read whole each caller file found by any tier that could break
6. Plan table: affected / intentionally untouched, with file:line from Read, and which
   tier found it
```

If every tier is red — still ship the plan: index (if any) + Grep + whole-file Read,
with an explicit "research limits" note; this lowers confidence, it does not skip the
gate.

---
