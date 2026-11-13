#!/usr/bin/env bash
# Копирует Git-состояние проекта вместе с .git в новую папку без harness.
# Секреты из рабочих файлов, база данных и незатреканные файлы не переносятся.
# История .git копируется как есть.
#
# Использование:
#   copy-project.sh --source DIR --target DIR [--force] [--include-tracked-changes] [--report FILE]
#
# Коды выхода:
#   0 успех
#   1 ошибка аргументов или Target уже существует
#   2 Source не является Git-репозиторием
#   3 найдено запрещённое к копированию состояние

set -euo pipefail

SOURCE=""
TARGET=""
FORCE=false
INCLUDE_TRACKED_CHANGES=false
REPORT=""

HARNESS_PATTERNS=(
  ".agents/"
  ".cursor/"
  ".codex/"
  ".kilo/"
  ".qoder/"
  ".qwen/"
  ".serena/"
  ".dsh/"
  ".codegraph/"
  ".codeprism.toml"
  ".cbmignore"
  ".doc/"
  "AGENTS.md"
)

usage() {
  cat <<'EOF'
Использование:
  copy-project.sh --source DIR --target DIR [--force] [--include-tracked-changes] [--report FILE]

Коды выхода:
  0 успех
  1 ошибка аргументов или Target уже существует
  2 Source не является Git-репозиторием
  3 нельзя скопировать .git: linked worktree, submodule, LFS или символическая ссылка
EOF
}

die() {
  local code="$1"
  shift
  echo "ERROR: $*" >&2
  exit "$code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) SOURCE="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    --force) FORCE=true; shift ;;
    --include-tracked-changes) INCLUDE_TRACKED_CHANGES=true; shift ;;
    --report) REPORT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die 1 "неизвестный аргумент: $1" ;;
  esac
done

[[ -n "$SOURCE" && -n "$TARGET" ]] || die 1 "нужны --source и --target"
[[ -d "$SOURCE" ]] || die 1 "Source не найден: $SOURCE"
git -C "$SOURCE" rev-parse --show-toplevel >/dev/null 2>&1 || die 2 "Source не Git-репозиторий: $SOURCE"

SOURCE_ROOT="$(git -C "$SOURCE" rev-parse --show-toplevel)"
SOURCE_ABS="$(realpath -m "$SOURCE_ROOT")"
TARGET_ABS="$(realpath -m "$TARGET")"

case "$TARGET_ABS/" in
  "$SOURCE_ABS/"*) die 1 "Target внутри Source запрещён" ;;
esac
case "$SOURCE_ABS/" in
  "$TARGET_ABS/"*) die 1 "Source внутри Target запрещён" ;;
esac

if [[ -e "$TARGET_ABS" && "$FORCE" != true ]]; then
  die 1 "Target уже существует: $TARGET_ABS. Используйте --force"
fi
[[ "$TARGET_ABS" != "/" ]] || die 1 "Target не может быть корнем файловой системы"

[[ -f "$SOURCE_ROOT/.gitmodules" ]] && die 3 "submodules не поддерживаются: найден .gitmodules"

LFS_FOUND=false
while IFS= read -r -d '' attrs; do
  if [[ -f "$SOURCE_ROOT/$attrs" ]] && grep -q 'filter=lfs' "$SOURCE_ROOT/$attrs"; then
    LFS_FOUND=true
  fi
done < <(git -C "$SOURCE_ROOT" ls-files -z '*.gitattributes')
[[ "$LFS_FOUND" == false ]] || die 3 "Git LFS не поддерживается: найден filter=lfs"

GIT_DIR_SRC="$SOURCE_ROOT/.git"
[[ -d "$GIT_DIR_SRC" && ! -L "$GIT_DIR_SRC" ]] || die 3 "Source .git должен быть каталогом: linked worktree, submodule и .git-файл не поддерживаются"

STAGING="${TARGET_ABS}.partial.$$"
trap 'rm -rf "$STAGING"' EXIT
mkdir -p "$STAGING"

COMMIT="$(git -C "$SOURCE_ROOT" rev-parse --short HEAD)"
BRANCH="$(git -C "$SOURCE_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo no-branch)"

is_harness() {
  local path="$1"
  local pattern
  for pattern in "${HARNESS_PATTERNS[@]}"; do
    case "$path" in
      "$pattern"|"$pattern"*) return 0 ;;
    esac
  done
  return 1
}

COPIED=0
EXCLUDED_HARNESS=0
EXCLUDED_SECRETS=0
LINK=0

is_secret_file() {
  local name="${1##*/}"
  case "$name" in
    .env|*.env|.env.*)
      case "$name" in
        *.example|*.dist|*.sample|*.template) return 1 ;;
        *) return 0 ;;
      esac
      ;;
  esac
  return 1
}

while IFS= read -r -d '' file; do
  if is_harness "$file"; then
    EXCLUDED_HARNESS=$((EXCLUDED_HARNESS + 1))
    continue
  fi
  if is_secret_file "$file"; then
    EXCLUDED_SECRETS=$((EXCLUDED_SECRETS + 1))
    continue
  fi
  if [[ -L "$SOURCE_ROOT/$file" ]]; then
    echo "ERROR: символическая ссылка в копируемом наборе: $file" >&2
    LINK=$((LINK + 1))
    continue
  fi
  mkdir -p "$STAGING/$(dirname "$file")"
  cp -p "$SOURCE_ROOT/$file" "$STAGING/$file"
  COPIED=$((COPIED + 1))
done < <(git -C "$SOURCE_ROOT" ls-files -z)

[[ "$LINK" -eq 0 ]] || die 3 "символические ссылки запрещены: $LINK"

TRACKED_CHANGES=0
if [[ "$INCLUDE_TRACKED_CHANGES" == true ]]; then
  CHANGED="$(
    {
      git -C "$SOURCE_ROOT" diff --name-only -z
      git -C "$SOURCE_ROOT" diff --cached --name-only -z
    } | tr '\0' '\n' | sort -u
  )"
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    is_harness "$file" && continue
    is_secret_file "$file" && continue
    [[ -f "$SOURCE_ROOT/$file" ]] || continue
    [[ -L "$SOURCE_ROOT/$file" ]] && die 3 "символическая ссылка: $file"
    mkdir -p "$STAGING/$(dirname "$file")"
    cp -p "$SOURCE_ROOT/$file" "$STAGING/$file"
    TRACKED_CHANGES=$((TRACKED_CHANGES + 1))
  done <<< "$CHANGED"
fi

UNTRACKED_TOTAL="$(git -C "$SOURCE_ROOT" ls-files --others --exclude-standard | wc -l | tr -d ' ')"

WORKTREES_REMOVED=0
if [[ -d "$GIT_DIR_SRC/worktrees" ]]; then
  WORKTREES_REMOVED="$(find "$GIT_DIR_SRC/worktrees" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
fi
cp -a "$GIT_DIR_SRC" "$STAGING/.git"
rm -rf "$STAGING/.git/worktrees"
rm -f "$STAGING/.git/index.lock" "$STAGING/.git/HEAD.lock" "$STAGING/.git/config.lock" "$STAGING/.git/shallow.lock"
mkdir -p "$STAGING/.git/info"
if ! grep -qxF '/STARTUP-REQUIRED.md' "$STAGING/.git/info/exclude" 2>/dev/null; then
  printf '\n# copy-project report\n/STARTUP-REQUIRED.md\n' >> "$STAGING/.git/info/exclude"
fi
git -C "$STAGING" rev-parse --git-dir >/dev/null 2>&1 || die 3 ".git не читается после копирования"
GIT_SIZE="$(du -sh "$STAGING/.git" | cut -f1)"
GIT_STATUS="$(git -C "$STAGING" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
REMOTES="$(git -C "$STAGING" remote 2>/dev/null | sort | tr '\n' ' ' | sed 's/ $//')"

ENV_TEMPLATES="$(cd "$STAGING" && find . -maxdepth 3 -path ./.git -prune -o -type f \( -name '.env.example' -o -name '.env.dist' -o -name '.env.sample' -o -name '*.env.example' \) -print | sort | sed 's|^\./||')"
COMPOSE_FILES="$(cd "$STAGING" && find . -maxdepth 3 -path ./.git -prune -o -type f \( -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' \) -print | sort | sed 's|^\./||')"
LOCK_FILES="$(cd "$STAGING" && find . -maxdepth 3 -path ./.git -prune -o -type f \( -name 'composer.lock' -o -name 'package-lock.json' -o -name 'yarn.lock' -o -name 'pnpm-lock.yaml' \) -print | sort | sed 's|^\./||')"
MIGRATION_DIRS="$(cd "$STAGING" && find . -maxdepth 3 -path ./.git -prune -o -type d \( -name migrations -o -name migrate -o -name sql \) -print | sort | sed 's|^\./||')"

ENV_KEYS="$(
  cd "$STAGING"
  grep -rhoE --exclude-dir=.git "getenv\(['\"][A-Z][A-Z0-9_]{2,}|\\\$_ENV\[['\"][A-Z][A-Z0-9_]{2,}|process\.env\.[A-Z][A-Z0-9_]{2,}" . 2>/dev/null \
    | grep -oE "[A-Z][A-Z0-9_]{2,}" \
    | sort -u || true
)"

REPORT_TMP="$STAGING/STARTUP-REQUIRED.md"

{
  echo "# Что нужно для запуска"
  echo
  echo "Источник: $SOURCE_ABS"
  echo "Коммит: $COMMIT"
  echo "Ветка: $BRANCH"
  echo "Скопировано файлов: $COPIED"
  echo "Tracked-изменений включено: $TRACKED_CHANGES"
  echo "Harness-путей исключено: $EXCLUDED_HARNESS"
  echo "Секретных env-файлов исключено: $EXCLUDED_SECRETS"
  echo "Незатреканных файлов не перенесено: $UNTRACKED_TOTAL"
  echo "Git-репозиторий: скопирован (.git целиком)"
  echo "Размер .git: $GIT_SIZE"
  echo "Worktree-регистраций удалено: $WORKTREES_REMOVED"
  echo "Незакоммиченных изменений в Target: $GIT_STATUS"
  echo "Remotes: ${REMOTES:-нет}"
  echo
  echo "## Не перенесено намеренно"
  echo
  echo "- секреты и значения переменных окружения;"
  echo "- база данных и дампы;"
  echo "- harness и документация агентов;"
  echo "- незатреканные и ignored файлы."
  echo
  echo "## Git"
  echo
  echo "- .git скопирован вместе с историей, ветками, remotes и hooks;"
  echo "- worktree-регистрации и lock-файлы удалены;"
  echo "- если harness или секретные env были tracked, в копии они показаны как удалённые;"
  echo "- секреты, попавшие в историю Git, не вычищаются."
  echo
  if [[ -n "$ENV_TEMPLATES" ]]; then
    echo "## Шаблоны окружения"
    echo
    while IFS= read -r line; do echo "- $line"; done <<< "$ENV_TEMPLATES"
    echo
  fi
  if [[ -n "$COMPOSE_FILES" ]]; then
    echo "## Compose-файлы"
    echo
    while IFS= read -r line; do echo "- $line"; done <<< "$COMPOSE_FILES"
    echo
  fi
  if [[ -n "$LOCK_FILES" ]]; then
    echo "## Зависимости"
    echo
    while IFS= read -r line; do echo "- $line"; done <<< "$LOCK_FILES"
    echo
  fi
  if [[ -n "$MIGRATION_DIRS" ]]; then
    echo "## Схема данных"
    echo
    while IFS= read -r line; do echo "- $line"; done <<< "$MIGRATION_DIRS"
    echo
  fi
  if [[ -n "$ENV_KEYS" ]]; then
    echo "## Переменные окружения, найденные в коде"
    echo
    echo "Значения не переносились. Заполните вручную или из хранилища секретов."
    echo
    while IFS= read -r key; do echo "- $key"; done <<< "$ENV_KEYS"
    echo
  fi
  echo "## Ручная проверка"
  echo
  echo "1. Сверить список переменных с шаблоном окружения."
  echo "2. Установить зависимости по lock-файлам."
  echo "3. Выбрать базу: внешняя, миграции или явный дамп."
  echo "4. Запустить приложение и пройти smoke-проверку."
  echo "5. Отметить незакрытые пункты перед статусом ready."
  echo
  echo "Подробный чек-лист: assets/startup-checklist.md в скиле copy-project."
} > "$REPORT_TMP"

if [[ -e "$TARGET_ABS" && "$FORCE" == true ]]; then
  rm -rf "$TARGET_ABS"
fi

mv "$STAGING" "$TARGET_ABS"
trap - EXIT

FINAL_REPORT="$TARGET_ABS/STARTUP-REQUIRED.md"
if [[ -n "$REPORT" ]]; then
  REPORT_DIR="$(dirname "$REPORT")"
  mkdir -p "$REPORT_DIR"
  cp "$FINAL_REPORT" "$REPORT"
  FINAL_REPORT="$REPORT"
fi

echo "Готово: $TARGET_ABS"
echo "Коммит: $COMMIT"
echo "Скопировано: $COPIED, harness исключён: $EXCLUDED_HARNESS, секретных env исключено: $EXCLUDED_SECRETS, tracked-изменений: $TRACKED_CHANGES"
echo "Git: .git $GIT_SIZE, worktrees удалено: $WORKTREES_REMOVED, изменений в Target: $GIT_STATUS"
echo "Отчёт: $FINAL_REPORT"
