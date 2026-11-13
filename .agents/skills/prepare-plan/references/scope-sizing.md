## Step P3.5 — Scope sizing (proportional decomposition)

Research depth (P1.2) and **plan artifact shape** are different axes.
P1.2 can stay thorough for safety; the written plan must not invent structure
the task does not need.

**Rule:** decompose by **independent reasons** to change code (separate AC, separate
entry/clone, separate shared risk) — never by the skill ritual or by editor micro-steps.

| Size | Signals (typical; any raise, do not force-up without signal) | Plan shape |
|------|--------------------------------------------------------------|------------|
| **Trivial** | 1 in-scope AC; 1 file (or paired template+locale for one string); P1.2 Low; not shared; no money/auth/DB | 1 Patch subsection; **no** Option B; **no** `stageN`; Verification = 1 literal step; optional empty sections = one-line `N/A` |
| **Small** | 1–2 files; one UI/HTTP contour; Low or Medium; shared only if already gated/opt-in in brief | 1–2 Patches; Option B only if a real trade-off exists; no artificial stages |
| **Medium** | 3+ files **or** 2+ independent AC **or** High risk **or** P2.7 multi-entry | Full template; Options A/B when the trade-off is real |
| **Large** | Critical; cross-feature shared default; money/auth mutation; brief spans multiple domains | Full template; split to `stageN` **only** after AskQuestion / new incident — never to "organize" one brief |

```
□ Classify size after P3, before Options/Patches; record in meta:
  scope_size: trivial | small | medium | large
□ Count independent reasons R (distinct AC needing different code, distinct
  entries/clones that must change, distinct shared risks) — not "open file",
  "find string", "save", "re-check"
□ Number of Patches subsections and implementation steps must track R
□ Trivial/Small: do not invent Option B, stage folders, Architecture essay, or
  IN/OUT tables when nothing shared is patched
□ P4.1 Architecture check: Trivial may be one line ("reuse N/A — string/copy
  change in place; sibling pattern = same file") — not a seven-bullet essay
□ Zero-ambiguity still applies: one complete Before/After + one literal
  expected result is enough for Trivial
□ Each R has one behavior scenario S under the P5 acceptance rule. Files of the
  same R cite that S instead of inventing per-file syntax scenarios
□ Self-check fails if Trivial/Small has >3 Patches steps for a single AC with no
  extra independent reason, or if stageN was created without new incident / user ask
□ Self-check fails if an R violates the P5 behavior-acceptance contract
```

**Anti-pattern:** "fix a page title" → 10 parts (docs sync, i18n refactor, CSS,
a11y pass, Option B via new component, stage2…). Correct: one template/locale
Patch + one verification string.

**Not an excuse to under-research:** Trivial still needs whole-file Read of the
patch file(s), unique Before, and the audit pass. Scope sizing collapses
**structure**, not **truth**.

---
