## Step P4 — Options and recommendation (minimal diff)

### P4.0 - Ponytail ladder (minimal complete change)

Before inventing code, take the first rung that fully works:

1. Does it need to exist? Skip features, options and flexibility nobody asked for;
   name them in Risks in one line.
2. Already in this codebase? Reuse the helper, component, service or pattern the
   way the surrounding code does.
3. Standard library or platform feature? Use it, unless the project has its own
   component. A house component beats a native widget.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise: the minimum code that works.

Do not cut validation at trust boundaries, error handling that prevents data loss,
security, accessibility, or anything the brief asks. Finish the callers, fixtures
and tests your change breaks.

This ladder does not override:

- P3.5 plan shape and closed task requirements from the brief;
- P4.1 architecture/SOLID/DRY gate and the project's layering;
- TEST_CANON resolved from ADAPTERS: every R still needs its S, and
  ponytail's one small test is a floor, not a replacement for the task matrix;
- project comment policy: do not add `shortcut:` comments unless the user asks.

Canonical instruction: [ponytail SKILL.md](../../ponytail/SKILL.md).

Minimality gate:

```
□ P3.5 scope_size recorded? Plan shape matches size (no ritual padding)
□ One-line / one-file fix for root cause?
□ Every listed file required? (drop cargo-cult)
□ Entry clones (second handler / second route) are NOT cargo-cult
□ Reuse existing method/pattern instead of new types?
□ New classes/tables/routes — only if unavoidable?
□ Shared file in Patches? → opt-in scoped to brief preferred over default-behavior change (P2.8)
□ Invariants from P3 preserved in every option that touches those paths?
□ Option B exists only for a real trade-off (Trivial/Small default = A only)
```

### P4.1 — Architecture / SOLID / DRY gate (required for every option)

Not a style preference — a correctness gate. A "minimal diff" that duplicates logic
or violates the project's layering is not minimal, it is a second maintenance point
and a future regression source.

```
□ Reuse (P3.6) checked before writing new code — new class/function/component only
  if nothing equivalent exists (cite the search: which tier, what was found/not found)
□ Single responsibility — this change does not mix layers the project already
  separates (e.g. no SQL/business logic added to a controller/route handler if the
  project's architecture doc places that in a service/repository layer)
□ DRY — if this is the 2nd+ occurrence of the same logic, extract to a shared
  unit instead of copy-pasting; if extraction is out of scope for this task, say so
  explicitly and note it as follow-up debt, do not silently duplicate
□ Open/closed — prefer an extension point (flag/hook/strategy/opt-in branch, P2.8)
  over broadening a shared function's default behavior
□ Dependency direction matches the project's documented layering (via DOCS_INDEX),
  not the reverse (e.g. a low-level helper must not reach back into a high-level
  service) — cite the architecture doc section, do not assert from memory
□ Naming/placement follows the convention of the module being touched (same folder,
  same suffix/prefix pattern as sibling files) — cite one sibling example
□ No new global/singleton/static mutable state introduced without an explicit reason
```

Record the result as one short subsection per chosen option: `### Architecture check`
with a pass/fail per bullet and a `file:line` or doc citation for each pass. A bullet
that cannot be justified from Read/docs fails the gate — fix the option, not the
checklist.

- Option A always; Option B (backup) **when useful** — required only if Medium/Large
  or a real trade-off on Small; Trivial = A only
- Default recommendation = smallest diff that still covers **all** brief criteria **and** does not alter OUT shared callers
- Equal size → prefer smaller side effects (callers Read whole)
- If A changes shared defaults and B uses opt-in: **prefer B** unless brief demands global UX

Before P5: all A files and blast callers already Read whole.

---
