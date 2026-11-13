#!/usr/bin/env bash
# Runs every harness self-test (skills, sync views, QA helpers).
#
# Why this exists: the harness ships regression tests for its own scripts, but
# nothing called them. A broken script (missing import) stayed broken because
# no gate, smoke step or CI file invoked the tests that already caught it.
#
# Usage:
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh          # run all
#   bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh --quiet  # only failures + summary
#
# Exit 0 when every suite passes, 1 otherwise.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../../../../" && pwd)"
cd "$ROOT_DIR" || exit 1

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

# Each entry is "path::expected_exit". Tests run via __main__ (stdlib only),
# so no pytest install is required.
SUITES=(
  ".agents/skills/harness-router/children/improvement/tests/test_harness_improvement.py"
  ".agents/skills/task-router/children/task-intake/tests/test_intake_state.py"
  ".agents/skills/task-router/children/task-intake/tests/test_intake_analysis.py"
  ".agents/skills/task-router/children/task-intake/tests/test_intake_orchestrator.py"
  ".agents/skills/task-router/children/task-intake/tests/test_doc_sections.py"
  ".agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_generate_report.py"
  ".agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_workflow_contract.py"
  ".agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_skill_integration.py"
  ".agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py"
  ".agents/skills/harness-router/children/environment-sync/tests/test_dsh_config.py"
  ".agents/skills/harness-router/children/environment-sync/tests/test_dsh_kit.py"
)

PASSED=0
FAILED=0
MISSING=0
FAILED_NAMES=()

for suite in "${SUITES[@]}"; do
  name="${suite##*/}"
  if [[ ! -f "$suite" ]]; then
    MISSING=$((MISSING + 1))
    echo "MISSING  $name"
    continue
  fi
  dir="$(dirname "$suite")"
  base="${name%.py}"
  output="$(cd "$dir" && timeout 300 python3 "$base.py" 2>&1)"
  rc=$?
  if [[ $rc -eq 0 ]]; then
    PASSED=$((PASSED + 1))
    [[ $QUIET -eq 0 ]] && echo "PASS     $name"
  else
    FAILED=$((FAILED + 1))
    FAILED_NAMES+=("$name")
    echo "FAIL     $name (exit $rc)"
    echo "$output" | tail -15 | sed 's/^/           /'
  fi
done

# Structural validators are mandatory too: they catch missing manifests, cards
# and script documents that unit suites do not know about.
VALIDATORS=(
  ".agents/skills/harness-router/children/improvement/scripts/validate_skills.py"
  ".agents/skills/harness-router/children/improvement/scripts/validate_docs.py"
  ".doc/web/bin/selfcheck.py"
)
for entry in "${VALIDATORS[@]}"; do
  name="${entry%% *}"
  name="${name##*/}"
  if python3 ${entry} >/tmp/selfcheck-validator.log 2>&1; then
    PASSED=$((PASSED + 1))
    [[ $QUIET -eq 0 ]] && echo "PASS     $name"
  else
    FAILED=$((FAILED + 1))
    FAILED_NAMES+=("$name")
    echo "FAIL     $name (exit $?)"
    tail -15 /tmp/selfcheck-validator.log | sed 's/^/           /'
  fi
done

echo
echo "selfcheck: $PASSED passed, $FAILED failed, $MISSING missing"
if [[ $FAILED -gt 0 ]]; then
  echo "failing: ${FAILED_NAMES[*]}"
  exit 1
fi
if [[ $MISSING -gt 0 ]]; then
  echo "selfcheck: suites are missing from the tree"
  exit 1
fi
exit 0
