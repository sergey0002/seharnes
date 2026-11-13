#!/usr/bin/env bash
# Тесты copy-project.sh на временных Git-репозиториях.
set -euo pipefail

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/copy-project.sh"
FAILS=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; FAILS=$((FAILS + 1)); }

make_repo() {
  local dir="$1"
  git init -q -b main "$dir"
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  mkdir -p "$dir/src" "$dir/.cursor/rules"
  printf '%s\n' '<?php echo getenv("APP_KEY");' > "$dir/src/app.php"
  printf '%s\n' '{}' > "$dir/composer.lock"
  printf '%s\n' 'APP_KEY=' > "$dir/.env.example"
  printf '%s\n' 'SECRET=real-value' > "$dir/.env"
  printf '%s\n' 'LOCAL_SECRET=real-value' > "$dir/config.env"
  printf '%s\n' 'rule' > "$dir/.cursor/rules/a.md"
  mkdir -p "$dir/.dsh/skills" "$dir/.codegraph"
  printf '%s\n' 'dsh kit' > "$dir/.dsh/skills/agent.md"
  printf '%s\n' 'graph index' > "$dir/.codegraph/index.db"
  printf '%s\n' 'prism config' > "$dir/.codeprism.toml"
  printf '%s\n' 'ignore config' > "$dir/.cbmignore"
  git -C "$dir" add -f src/app.php composer.lock .env.example .env config.env \
    .cursor/rules/a.md .dsh/skills/agent.md .codegraph/index.db .codeprism.toml .cbmignore
  git -C "$dir" commit -q -m init
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SRC="$TMP/source"
make_repo "$SRC"

# 1. Успешный перенос, harness и секреты исключены, ключ найден в отчёте.
OUT="$TMP/out1"
if bash "$SCRIPT" --source "$SRC" --target "$OUT" >/dev/null 2>&1; then
  pass "успешный перенос"
else
  fail "успешный перенос"
fi
[[ -f "$OUT/src/app.php" ]] && pass "tracked файл скопирован" || fail "tracked файл не скопирован"
[[ -d "$OUT/.git" ]] && pass ".git скопирован" || fail ".git не скопирован"
[[ "$(git -C "$OUT" rev-parse --short HEAD 2>/dev/null)" == "$(git -C "$SRC" rev-parse --short HEAD)" ]] && pass "коммит совпадает" || fail "коммит не совпадает"
STATUS_BAD="$(git -C "$OUT" status --porcelain 2>/dev/null | grep -v '^ D ' || true)"
[[ -z "$STATUS_BAD" ]] && pass "в копии только удаления исключённых файлов" || fail "неожидаемые изменения: $STATUS_BAD"
[[ ! -f "$OUT/.env" ]] && pass "секрет не скопирован" || fail "секрет попал в Target"
[[ ! -f "$OUT/config.env" ]] && pass "tracked config.env исключён" || fail "tracked config.env попал в Target"
[[ -f "$OUT/.env.example" ]] && pass "шаблон env сохранён" || fail "шаблон env исключён"
[[ ! -d "$OUT/.cursor" ]] && pass "harness исключён" || fail "harness попал в Target"
[[ ! -d "$OUT/.dsh" ]] && pass "tracked DSH kit исключён" || fail "DSH kit попал в Target"
[[ ! -d "$OUT/.codegraph" ]] && pass "индекс CodeGraph исключён" || fail "индекс CodeGraph попал в Target"
[[ ! -f "$OUT/.codeprism.toml" && ! -f "$OUT/.cbmignore" ]] && pass "служебные config-файлы исключены" || fail "служебные config-файлы попали в Target"
grep -q "APP_KEY" "$OUT/STARTUP-REQUIRED.md" && pass "переменная найдена" || fail "переменная не найдена"

# 1b. Worktree-регистрации исходного репозитория не попадают в копию.
git -C "$SRC" worktree add -q "$TMP/wt" -b wt-branch
OUT_GIT="$TMP/out-git"
if bash "$SCRIPT" --source "$SRC" --target "$OUT_GIT" >/dev/null 2>&1; then
  pass "перенос с worktree в источнике"
else
  fail "перенос с worktree в источнике"
fi
[[ -d "$OUT_GIT/.git" ]] && pass ".git скопирован при worktree в источнике" || fail ".git не скопирован"
[[ ! -e "$OUT_GIT/.git/worktrees" ]] && pass "worktree-регистрации удалены" || fail "worktree-регистрации попали в копию"
STATUS_BAD_GIT="$(git -C "$OUT_GIT" status --porcelain 2>/dev/null | grep -v '^ D ' || true)"
[[ -z "$STATUS_BAD_GIT" ]] && pass "копия с worktree без лишних изменений" || fail "неожидаемые изменения: $STATUS_BAD_GIT"

# 1c. Linked worktree как Source даёт код 3.
set +e
bash "$SCRIPT" --source "$TMP/wt" --target "$TMP/out-wt" >/dev/null 2>&1
CODE=$?
set -e
[[ "$CODE" -eq 3 ]] && pass "linked worktree отвергнут" || fail "код linked worktree: $CODE"
git -C "$SRC" worktree remove --force "$TMP/wt" >/dev/null 2>&1 || true

# 1d. Репозиторий без tracked harness: копия чистая.
SRC_CLEAN="$TMP/source-clean"
git init -q -b main "$SRC_CLEAN"
git -C "$SRC_CLEAN" config user.email test@example.com
git -C "$SRC_CLEAN" config user.name test
printf '%s\n' '<?php' > "$SRC_CLEAN/app.php"
git -C "$SRC_CLEAN" add app.php
git -C "$SRC_CLEAN" commit -q -m init
OUT_CLEAN="$TMP/out-clean"
if bash "$SCRIPT" --source "$SRC_CLEAN" --target "$OUT_CLEAN" >/dev/null 2>&1; then
  pass "перенос репозитория без tracked harness"
else
  fail "перенос репозитория без tracked harness"
fi
[[ "$(git -C "$OUT_CLEAN" status --porcelain 2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]] && pass "git status чистый" || fail "git status не чистый"

# 2. Существующий Target без --force даёт код 1.
set +e
bash "$SCRIPT" --source "$SRC" --target "$OUT" >/dev/null 2>&1
CODE=$?
set -e
[[ "$CODE" -eq 1 ]] && pass "существующий Target отвергнут" || fail "код для существующего Target: $CODE"

# 3. Target внутри Source даёт код 1.
set +e
bash "$SCRIPT" --source "$SRC" --target "$SRC/inside" >/dev/null 2>&1
CODE=$?
set -e
[[ "$CODE" -eq 1 ]] && pass "вложенный Target отвергнут" || fail "код вложенного Target: $CODE"

# 4. Submodules дают код 3.
printf '%s\n' '[submodule "x"]' > "$SRC/.gitmodules"
git -C "$SRC" add .gitmodules && git -C "$SRC" commit -q -m submodules
set +e
bash "$SCRIPT" --source "$SRC" --target "$TMP/out4" >/dev/null 2>&1
CODE=$?
set -e
[[ "$CODE" -eq 3 ]] && pass "submodules отвергнуты" || fail "код submodules: $CODE"
rm -f "$SRC/.gitmodules"
git -C "$SRC" rm -q --cached .gitmodules >/dev/null 2>&1 || true
git -C "$SRC" commit -q -m remove-submodules 2>/dev/null || true

# 5. Символическая ссылка даёт код 3.
ln -s src/app.php "$SRC/link.php"
git -C "$SRC" add link.php
git -C "$SRC" commit -q -m symlink
set +e
bash "$SCRIPT" --source "$SRC" --target "$TMP/out5" >/dev/null 2>&1
CODE=$?
set -e
[[ "$CODE" -eq 3 ]] && pass "символическая ссылка отвергнута" || fail "код symlink: $CODE"

echo
if [[ "$FAILS" -eq 0 ]]; then
  echo "Все тесты пройдены"
  exit 0
fi
echo "Провалено тестов: $FAILS"
exit 1
