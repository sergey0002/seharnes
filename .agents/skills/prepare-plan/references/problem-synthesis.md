## Step P3 — Problem synthesis

Before solution options:

1. **Symptom** — user / log / staging
2. **Reproduction** — entries from **P2.7**, not one screenshot path
3. **As-is** — call chain with `file:line` (**from code Read**, not docs alone)
4. **Root cause** — one sentence with quotes from Read (`file:line`)
5. **Impact / blast radius** — per P1.2 risk level per file; tool-ladder callers (name
   which tier found each) + whole-file Read; in/out table; git-task-blame table (P0.5b)
6. **Reuse** — cite the **existing** pattern/service/helper/commit in this repo that
   already does this or something equivalent (file:line); "none found" only after
   Tier 0/3 search, not from memory — feeds P4 architecture gate
7. **Out of scope** — explicit "do not touch" with Read-based reason
8. **Invariants** — contracts that must survive the diff (from P0.5/P0.5b prior work,
   same-file guards, dual HTTP preview/commit). Empty section only if none found after search.
9. **Docs ≠ code** — if P0.6 found mismatch, one line here

If task notes disagree with architecture — mention; do **not** rewrite architecture here (that is a separate doc skill after merge).

---

