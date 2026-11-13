---
name: task-code-review
description: Review a Bitbucket task strictly by its own commits and task diff artifacts. Use when the user asks for task code review, review task diff, audit task changes, verify whether a hunk/file really belongs to a task, or asks to clean up a task diff safely. Limit review to files listed in `.doc/tasks/{N}/diff.files.md`, verify hunk ownership against task commits from `.doc/tasks/{N}/diff.md`, and avoid touching unrelated legacy code in the same files.
---

# Task Code Review

Review only the task's own changes. Treat nearby legacy code as out of scope until proven otherwise.

## Inputs

Use these artifacts first:

1. `.doc/tasks/{N}/diff.md` ? commit list and summary for the task.
2. `.doc/tasks/{N}/diff.files.md` ? file list for the task diff.
3. Source files from that file list.
4. `git show <task-commit> -- <file>` and `git blame -L start,end -- <file>` for ownership checks.

If the user explicitly asks to refresh task diff, use the `task-diff` project skill before review. Do not refresh diff by default if the current task diff already exists.

## Core rule

For every disputed or cleanup candidate hunk, follow this sequence exactly:

1. Take a concrete hunk, not the whole file.
2. Check which commit introduced that hunk.
3. If the hunk was not introduced by the task commits from `diff.md`, do not change it and do not treat it as task scope.
4. If the hunk was introduced by the task commits, then decide whether it is necessary, risky, or removable.

Never infer ownership from proximity inside the file. Never clean up a large file only because it looks related.

## Review workflow

### 1. Lock scope

- Read task number `N` from user context or current task docs.
- Read `.doc/tasks/{N}/diff.md` and collect the exact task commit hashes.
- Read `.doc/tasks/{N}/diff.files.md` and limit review to those files.

### 2. Review file by file

For each file in `diff.files.md`:

- Inspect the task hunks in the current branch diff.
- Compare them with `git show <task-commit> -- <file>` across the task commits.
- If ownership is unclear, use `git blame` on the exact line range.

### 3. Classify each hunk

Classify each reviewed hunk as one of:

- **Required** ? directly implements or supports the task.
- **Reasonable but optional** ? improves diagnostics, UX, or reliability without changing business scope.
- **Suspicious** ? task-owned but risky, redundant, temporary, or too broad.
- **Out of scope** ? not introduced by task commits; leave untouched.

### 4. Validate impact

For every task-owned hunk that remains in scope, check:

- Does it implement a task requirement or a necessary fix?
- Does it alter unrelated providers, flows, routes, or shared helpers?
- Does it add debug output, temporary guards, or task-local hacks that should be removed before merge?
- Does it preserve existing project behavior outside the task scenario?

### 5. Propose cleanup safely

Only propose or apply cleanup when both are true:

- the exact hunk is proven to belong to the task commits;
- the cleanup is justified by task scope, safety, or removal of temporary or debug code.

If a file contains both legacy code and task code, modify only the proven task hunks.

## Minimality lens

After ownership is proven, check whether the task hunk is larger than needed.
Use the [ponytail review lens](../ponytail/references/review.md) and the
[ponytail skill](../ponytail/SKILL.md). The lens only flags over-engineering:
required behavior, safety, error handling, tests and task ownership win.

## Guardrails

- Do not rollback entire files when only one task hunk is problematic.
- Do not use current `git diff` alone as proof of task ownership.
- Do not treat old blame lines as task changes even if the file is listed in `diff.files.md`.
- Do not remove business text, messages, or logic from older tasks unless the user explicitly broadens scope.
- Do not claim that all changes in a file belong to the task without commit-level proof.

## Good evidence

Strong evidence that a hunk belongs to the task:

- the hunk appears in `git show <task-commit> -- <file>`;
- blame on that line range points to a commit listed in `.doc/tasks/{N}/diff.md`;
- the hunk matches the task purpose and branch history.

Weak evidence that is not enough on its own:

- the file appears in `diff.files.md`;
- the code is near task code;
- the code looks semantically related.

## Output format

When reporting review results, separate findings into:

1. **Confirmed task-owned changes**
2. **Confirmed out-of-scope legacy changes**
3. **Risks / regressions**
4. **Safe cleanup candidates**

When you say a hunk is out of scope, cite the proof briefly, for example:

- `git blame` points to a commit that is not listed in `.doc/tasks/{N}/diff.md`
- the hunk appears in `git show` for a task commit, so it is task-owned

## Applying fixes after review

If the user asks to fix issues after review:

1. Reuse the same ownership discipline.
2. Patch only proven task hunks.
3. Re-run targeted checks relevant to the touched files.
4. Summarize exactly what changed and why it was safe.
