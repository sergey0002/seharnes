# Catalog of Skill Smells, MAST Failure Modes & Security Signatures

Use this catalog during static and semantic audits to tag findings with standardized codes.
**Frontier-First Calibration:** Modern frontier models perform best with **high information density, clear invariants, and path freedom** — never force unnecessary boilerplate. Structural smells (`BG`, `TSW`, `ME`, `NPT`, `MUS`, `SOC`) apply **only** when missing clarity actually causes risk, while **`CAGE`** flags prompts that suffocate strong models with arbitrary numerical quotas or rigid prose choreography.

---

## Part A: 26 Empirical `SKILL.md` Skill Smells (Hong et al., 2026 — `arXiv:2607.01456`)

| Code | Smell Name | Category | Detection Rule / Meaning | Prevalence |
|---|---|---|---|---|
| **RL** | Rationalization Loophole | Missing Follow-Through Guards | No explicit anti-shortcut rules discouraging agent from skipping validation/steps | 94% |
| **BG** | Buried Gotchas | Missing Safeguards | Critical caveats buried in prose instead of prominent `## Gotchas` / warning blocks | 81% |
| **EWP** | Execute Without a Plan | Missing Verification Loop | Directs complex/batch/destructive work without an intermediate plan-validate step | 78% |
| **NAH** | Never Asks Human | Missing Verification Loop | Zero escalation / confirmation mechanism when ambiguous or high-risk | 77% |
| **NPT** | No Progress Tracking | Missing Follow-Through Guards | Multi-step workflow lacks checklist or external progress tracking (`todo.md`) | 71% |
| **MC** | Missing Caveats | Missing Safeguards | Omits common failure conditions, edge cases, and resolutions | 71% |
| **NVS** | No Validation Step | Missing Verification Loop | Treats output generation as one-shot without checking/testing output | 69% |
| **MDT** | Missing Decision Tree | Under-Specified Guidance | Multiple branching scenarios lack an explicit decision table/tree | 69% |
| **NG** | No Guardrails | Missing Safeguards | Lacks scope refusals / constraints against impossible or dangerous tasks | 67% |
| **MUS** | Missing Utility Script | Under-Specified Guidance | Repeatable deterministic computation/parsing left to LLM improvisation | 66% |
| **SCRIPT-OVERREACH** | Script Semantic Usurpation | Over-Engineered Script | Script attempts NLP/semantic text parsing, fragile keyword/regex judgment of meaning/tone/fluff, or duplicates native LLM reasoning instead of delegating to the model | Frontier |
| **SCRIPT-EXEC-BIT-TRAP** | Interpreter-less Script Call | Portability / Runtime Bug | Invokes `./scripts/tool.sh` directly without explicit `bash` / `python3`; plugin packagers often strip executable `+x` bits | Frontier |
| **PORT-VENDOR-LOCK** | Client / Tool Syntax Lock-In | Portability Failure | Body relies on Claude/vendor-only constructs (`!`command``, unguarded `${CLAUDE_SKILL_DIR}`/`$ARGUMENTS`, hardcoded `~/.claude/`/`.qoder/` paths, or exclusive tool names like `MultiEdit`/`grep_search`/`execute_command`) without portable fallback | Cross-Agent |
| **PORT-PATH-SILO** | Narrow Auto-Discovery Path | Discoverability Gap | Deployed solely in a single-vendor dir (`.claude/skills/`, `.qoder/skills/`, `.kiro/skills/`) instead of universal `.agents/skills/` + multi-agent install (`npx skills add`), silently hiding skill from 10+ agents | Cross-Agent |
| **PORT-FRONTMATTER-DRIFT** | Silent Cross-Agent Frontmatter Loss | Portability Drift | Critical behavior/safety depends on non-portable extensions (`context: fork`, `disable-model-invocation` without `openai.yaml`/`opencode/autoinvoke`, `allowed-tools` in Cursor/Kiro, non-string `metadata` for OpenCode, or keys outside 6-key core whitelist) | Cross-Agent |
| **PORT-NONCANONICAL-DIR** | Non-Canonical Subdirectory Dialect | Structural Drift | Uses dialect folders (`resources/`, `docs/`, `examples/`, `templates/`) or flat `.md` instead of canonical `<name>/SKILL.md` + `scripts/`, `references/`, `assets/` | Cross-Agent |
| **CSO-LEAK** | Workflow Leak in Description | Under-Loading Risk | Frontmatter `description` summarizes internal step-by-step algorithm so strong models execute from the catalog entry alone and skip reading `SKILL.md` gotchas | Frontier |
| **UNREQ-ESCALATION** | Unrequested Audit / Scope Escalation | Over-Triggering / Scope Creep | Specialized audit/hardening skill triggers on ordinary adjacent tasks, or treats approval of one action as blanket permission expansion | Frontier |
| **MD-UNCLOSED-FENCE** | Unbalanced Code Fence | Syntax Breakage | Unclosed triple-backtick (` ``` `) or tilde (`~~~`) fence inside Markdown corrupts model instruction parsing | Static |
| **SG07-SPOOFING** | Manifest-vs-Code Spoofing | Deceptive / Drift Risk | `description` or `allowed-tools` claims narrow scope while scripts perform broader network/filesystem mutations | High |
| **SG09-PRIVILEGE-CHAIN** | Cross-Skill Privilege Chaining (Lethal Trifecta) | Fleet / Bundle Hazard | Multiple skills in a bundle/fleet combine untrusted input + sensitive filesystem read + network egress even when each skill appears benign alone | Bundle/Fleet |
| **SOC** | Series of Commands | Over-Prescribed Guidance | Rigid line-by-line hardcoded shell commands where adaptive reasoning is needed | 62% |
| **CAGE** | Over-Constrained Frontier Cage | Over-Prescribed Guidance | Arbitrary numeric quotas (`exact N bullets/sentences`), forced thought choreography, or micromanagement that degrades strong models | Frontier |
| **SCAR** | Weak-Model Scar Tissue | Legacy Over-Prompting | Outdated compensating crutches (*"think step by step", "double-check every number before answering", "if in doubt MUST call X"*) causing over-verification/over-triggering on frontier reasoning models, or bare `NEVER` walls without positive alternatives | Frontier |
| **FLUFF** | Zero-Gain Filler / Water | Context Bloat / Low Signal | Generic platitudes or textbook truisms (*"write clean code", "follow best practices", "be thorough"*) adding zero unique domain heuristics or invariants | High |
| **AMBIG** | Non-Self-Contained Thesis | Inadequate Grounding | Rules, pronouns, or acronyms requiring external chat/repo lore (*"as discussed", "our standard", "that file", "etc."*) instead of explicit artifact + condition + observable criteria | High |
| **CONTRA** | Internal Contradiction | Coherence Failure | Mutually conflicting instructions across `description ↔ SKILL.md ↔ agents/ ↔ references/ ↔ scripts/` or colliding rules lacking precedence order | Critical |
| **UD** | Undelegated Detail | Context Bloat | Low-level API manuals/schemas embedded in `SKILL.md` instead of `references/` | 46% |
| **MUR** | Missing Usage Rules | Missing Safeguards | Omits explicit rules on when/how the skill or sub-components apply | 44% |
| **ME** | Missing Example | Inadequate Grounding | No concrete input/output examples where format/behavior is non-trivial | 34% |
| **TSW** | The Stepless Workflow | Under-Specified Guidance | Entire multi-stage task written as an unstructured prose wall without numbered steps | 32% |
| **CSD** | Confusing Skill Description | Context Bloat / Trigger | Frontmatter `description` lacks `[What] + [When] + [Keywords]` | 32% |
| **MT** | Missing Template | Unstructured Output | Expects structured output without providing a concrete template/schema | 25% |
| **USN** | Unclear Skill Name | Convention Violation | `name` does not clearly convey capability (e.g., `helper`, `misc`, `dig`) | 17% |
| **TOB** | The Option Buffet | Under-Specified Guidance | Lists multiple tools/libraries as equal choices without recommending a default | 8% |
| **TSS** | Time Sensitive Skill | Inadequate Grounding | Hardcodes volatile dates, transient versions, or perishable claims | 3% |
| **NTPD** | Non Third Person Description | Convention Violation | `description` written in 1st/2nd person ("I help you...") instead of 3rd person/imperative | 3% |
| **BP** | Backslash Path | Convention Violation | Uses Windows backslashes (`scripts\run.py`) instead of forward slashes (`scripts/run.py`) | 1% |
| **LSB** | Always-On Rule Bloat | Context Bloat | `alwaysApply: true` rule spends a large token budget on every turn; scope it with globs or description | <1% |
| **XID** | XML Included Description | Security Hazard | Frontmatter `description` contains `<...>` XML tags (prompt injection surface) | 0% |

---

## Part B: 14 Multi-Agent System Failure Modes — MAST Taxonomy (Cemri et al., NeurIPS 2025 — `arXiv:2503.13657`)

### FC1. System Design Issues (~41.8% of failures)
- **FM-1.1 Disobey Task Specification**: Role/task boundaries are ambiguous, causing agents to violate constraints or drift out of scope.
- **FM-1.2 Disobey Role Specification**: Worker assumes orchestrator duties or edits files when scoped as read-only reviewer.
- **FM-1.3 Step Repetition**: Agent loops on already completed steps due to missing progress tracking or `maxTurns` caps.
- **FM-1.4 Loss of Conversation History**: Context truncation/compaction drops vital constraints mid-handoff.
- **FM-1.5 Unaware of Termination Conditions**: Missing explicit "Done When" / convergence rules cause infinite refinement loops.

### FC2. Inter-Agent Misalignment (~36.9% of failures)
- **FM-2.1 Conversation Reset**: Subagent restarts without receiving required state summary from predecessor.
- **FM-2.2 Fail to Ask for Clarification**: Agents guess on underspecified handoffs instead of escalating/clarifying.
- **FM-2.3 Task Derailment**: Worker pursues tangential exploration unrelated to parent objective.
- **FM-2.4 Information Withholding**: Subagent returns summary omitting critical caveats, file paths, errors, or schema formats needed by next agent.
- **FM-2.5 Ignored Other Agent's Input**: Orchestrator or downstream worker ignores constraints or findings returned by upstream agent.
- **FM-2.6 Reasoning-Action Mismatch**: Agent's stated plan contradicts the tools/actions it invokes.

### FC3. Task Verification & Quality Control (~21.3% of failures)
- **FM-3.1 Premature Termination**: Orchestrator declares completion before all required workers/checks finish.
- **FM-3.2 No or Incomplete Verification**: Outputs accepted without deterministic checks or skeptical review.
- **FM-3.3 Incorrect Verification**: Rubber-stamp verifier approves flawed work due to shared biased context or weak criteria (fix: blind/isolated verifier with explicit evidence requirements).

---

## Part C: Security Threat & Anti-Pattern Signatures (Snyk ToxicSkills / OWASP AST / TAR Engine 2026)

| Code | Severity | Pattern |
|---|---|---|
| **SEC-PIPE-SHELL** | CRITICAL | `curl ... \| bash`, `wget ... \| sh`, `iex (irm ...)` — remote unverified code execution |
| **SEC-REMOTE-INSTR** | CRITICAL | Instructing agent to fetch and obey remote markdown/prompts at runtime (`curl .../rules.md`) |
| **SEC-PROMPT-INJ** | CRITICAL | Direct override phrases (`ignore previous instructions`, `bypass safety`), zero-width Unicode (`\u200b`–`\u200f`, `\ufeff`), hidden HTML comment directives |
| **SEC-SECRET-LEAK** | CRITICAL | Hardcoded API keys, tokens (`sk-...`, `ghp_...`, `AKIA...`, private key headers) inside skill files |
| **SEC-EXFIL-VECTOR** | CRITICAL | Reading `.env`, `~/.ssh`, `~/.aws`, browser cookies/keychains combined with outbound network transfer |
| **SEC-MEM-POISON** | CRITICAL | Unauthorized writes to persistent agent memory (`MEMORY.md`, global `~/.claude/CLAUDE.md`, `AGENTS.md`) |
| **SEC-EVAL-EXEC** | HIGH | Unsanitized `eval()`, `exec()`, `subprocess(..., shell=True)`, `os.system()` on dynamic inputs |
| **SEC-UNTRUSTED-DATA** | HIGH | Missing boundary warning when processing external web/MCP/repo outputs (indirect prompt injection vector) |
| **SEC-UNBOUNDED-DESTRUCT** | HIGH | Irreversible operations (`rm -rf`, `DROP TABLE`, `git push --force`, production deploy, payments) without HITL confirmation or `--dry-run` |
| **SEC-UNPINNED-DEP** | MEDIUM | Floating dependencies (`@latest`, `*`, `^`, unpinned `pip install` without hash/version range) |
| **SEC-EXCESS-TOOLS** | MEDIUM | Overly broad `allowed-tools` (e.g., unrestricted `Bash` for a read-only linting/review skill) |
| **SEC-SYMLINK-ESCAPE** | CRITICAL | Symlink inside skill resolves outside the skill root (credential/host escape or broken marketplace cache) |
| **SEC-LOADTIME-EXEC** | HIGH | Unreviewed inline `!command` template expansion or frontmatter `hooks:` executing automatically at skill load |
| **SEC-IMG-METADATA** | HIGH | Hidden text instructions embedded in PNG `tEXt`/`iTXt`/`zTXt` metadata chunks (`assets/*.png`) |
| **SEC-PYC-BYTECODE** | HIGH | Compiled Python bytecode (`.pyc`/`.pyo`) shipped inside skill package (integrity & coverage blind spot) |
| **SEC-AUTO-EXEC-TEST** | HIGH | Auto-discovered test files (`conftest.py`, `test_*.py`, `*.test.js`) outside `evals/`/`tests/` executed by test runners |
| **SEC-PKG-LIFECYCLE** | HIGH | Automatic npm lifecycle scripts (`preinstall`/`install`/`postinstall`) in bundled `package.json` |
| **SEC-TYPOSQUAT** | HIGH | Dependency name in PEP 723 / `requirements.txt` / `package.json` within edit distance 1–2 of popular PyPI/npm packages (`SG10`) |
