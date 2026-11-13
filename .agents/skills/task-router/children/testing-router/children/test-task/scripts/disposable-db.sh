#!/usr/bin/env bash
# Create or drop a disposable MySQL database for QA migration/unit phases.
set -euo pipefail

PHASE="${1:-create}"
RUN_ID="${2:-manual}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../../../../" && pwd)"
ENV_FILE="${ROOT_DIR}/.tools/docker-dev/.env"
if [ ! -f "$ENV_FILE" ] && [ -f "${ROOT_DIR}/tools/docker-dev/.env" ]; then
    ENV_FILE="${ROOT_DIR}/tools/docker-dev/.env"
fi

read_env() {
    local key="$1" default="$2"
    if [ -f "$ENV_FILE" ]; then
        local value
        value="$(awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE")"
        printf '%s' "${value:-$default}"
    else
        printf '%s' "$default"
    fi
}

MYSQL_CONTAINER="${QA_MYSQL_CONTAINER:-copytrust-dev-mysql-1}"
MYSQL_ROOT_USER="${MYSQL_ROOT_USER:-$(read_env MYSQL_ROOT_USER root)}"
MYSQL_ROOT_PASS="${MYSQL_ROOT_PASS:-$(read_env MYSQL_ROOT_PASSWORD root_password)}"
SOURCE_DB="${QA_SOURCE_DB:-$(read_env MYSQL_DATABASE gb_copydev5)}"
DB_NAME="${QA_DB_NAME:-${SOURCE_DB}_qa_${RUN_ID//[^a-zA-Z0-9]/_}}"

mysql_root() {
    docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASS" "$@"
}

case "$PHASE" in
    create)
        if [ "$RUN_ID" = "$SOURCE_DB" ] || [ "$RUN_ID" = "gb_copydev5" ] || [ "$DB_NAME" = "$SOURCE_DB" ] || [ "$DB_NAME" = "gb_copydev5" ]; then
            printf 'refusing to use shared database: %s\n' "$DB_NAME" >&2
            exit 2
        fi
        mysql_root -e "DROP DATABASE IF EXISTS ${DB_NAME}; CREATE DATABASE ${DB_NAME};"
        if docker exec "$MYSQL_CONTAINER" sh -lc "command -v mysqldump >/dev/null"; then
            docker exec "$MYSQL_CONTAINER" mysqldump -u"$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASS" --no-data --routines --triggers "$SOURCE_DB" \
                | docker exec -i "$MYSQL_CONTAINER" mysql -u"$MYSQL_ROOT_USER" -p"$MYSQL_ROOT_PASS" "$DB_NAME"
        else
            printf 'mysqldump is required in %s\n' "$MYSQL_CONTAINER" >&2
            exit 3
        fi
        printf 'QA_DB_NAME=%s\nQA_DB_SOURCE=%s\n' "$DB_NAME" "$SOURCE_DB"
        ;;
    drop)
        mysql_root -e "DROP DATABASE IF EXISTS ${DB_NAME};"
        printf 'dropped %s\n' "$DB_NAME"
        ;;
    *)
        printf 'usage: %s create|drop [run-id]\n' "$0" >&2
        exit 2
        ;;
esac
