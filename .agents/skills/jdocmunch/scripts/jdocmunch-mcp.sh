#!/usr/bin/env bash
# jDocMunch MCP launcher (canonical for every agent environment).
#
# Canon lives in .agents/skills/jdocmunch/scripts/, mirrors of skills are
# produced by
# .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh and copy-dsh-kit.ps1. Never edit the
# mirrors: see .doc/harnes/state/13-agent-migration.md.
#
# The index is shared by every project on this machine and keyed by
# owner/name under $DOC_INDEX_PATH:
#
#   <owner>/<name>.json                 main index
#   <owner>/<name>.related.json         link/parent graph
#   <owner>/<name>.postings.jsonl       BM25 postings
#   _groups.jsonc                       repo groups
#
# Embeddings are OFF since 2026-11-03. Benchmark on 22 queries showed lexical
# is more accurate overall: Hit@3 0.59 against 0.45 for the default hybrid and
# 0.27 for semantic-only. See .doc/harnes/mcp/jdocmunch.md, section "Бенчмарк
# поиска", and .doc/skil_data/jdocmunch/benchmark/.
#
# Nothing here is pinned to one project path on purpose: the project root is
# derived from this script's own location, and the repo handle is resolved from
# the index metadata (source_root) or overridden by env. That is what makes the
# same canon work after copy-dsh-kit or rebase_project.ps1 moved it.
#
# Why a wrapper and not a direct `jdocmunch-mcp` call:
#
#  1. Embeddings are disabled here on purpose. The lexical index is enough and
#     the vector sidecar is not built, so no model is downloaded or loaded.
#  2. The MCP server reads DOC_INDEX_PATH at CALL time, so pinning it here keeps
#     this project from seeing another project's index unless told to.
#
# Index maintenance (run by hand, not by the server):
#   bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index              # refresh
#   bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --corpus             # how many files the run would index
#
# Corpus: `architecture harnes tasks web` under DOCROOT. `web` contributes the
# Markdown documentation of the local panel (`.doc/web/README.md`); PHP, JS and
# CSS there are not Markdown and stay out. Pruned: generated run
# artifacts (`test-runs/`, `tests/`, `reports/`, `backups/`, `backup-*`,
# `_jsondoc/`, `_dialogs/`, `dialogs/`) and generated architecture views
# (`business-rules/`, `technical-facts/`, `ui-rules/`), because they repeat
# the same knowledge thousands of times. Override with `JDOCMUNCH_CORPUS`.
#
# Optional env overrides, used when this kit is copied into another project:
#   JDOCMUNCH_DOCROOT      documentation root to index (default <root>/.doc)
#   JDOCMUNCH_CORPUS       space separated subdirectories (default above)
#   JDOCMUNCH_INDEX_NAME   index name under local/ (default from resolved repo)
#   JDOCMUNCH_REPO         repo handle for --repo / --index (default resolved)
#   DOC_INDEX_PATH         index store (default ~/.doc-index)
#
# Why .doc/ is indexed with exclusions rather than as-is:
#
#   .doc/ is 3.8 GB / 4346 Markdown files, but only 21.5 MB / 1618 of them are
#   real documentation. The rest is generated or third-party:
#
#     backups/             1.4 GB   timestamped snapshots of the same corpus
#     jsondoc_scripts/     240 MB   2590 md, ALL under runs/*/sandbox/
#     codeception/vendor/  118 MB   phpunit and friends, upstream READMEs
#     codeception/tests/            generated Codeception suites
#     gb_copydev5.sql      197 MB   a database dump, not Markdown at all
#
#   Patterns below are gitignore syntax and are PERSISTED with the index, so a
#   later refresh that omits the flags inherits them instead of widening the
#   corpus back to 4346 files. `--no-extra-ignore-patterns` clears them.
#
# Model choice (measured on this machine, 2026-10-30, 6 Russian pairs):
#   paraphrase-multilingual-mpnet-base-v2  1.0 GB, 512 ctx, ru margin 0.223
#   embeddinggemma-300m                    1.24 GB, 2048 ctx, ru margin 0.341
#     but 3.3 s/section on CPU. Rejected on speed.
#   MiniLM-L12                             0.22 GB, 128 ctx, truncates 41.7%
#     of sections. Rejected on quality.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
find_project_root() {
  local dir="${1:-}"
  while [ "$dir" != "/" ]; do
    if [ -d "$dir/.cursor" ] || [ -d "$dir/.git" ]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}
PROJECT="$(find_project_root "$SCRIPT_DIR")" || { echo "jdocmunch: project root not found" >&2; exit 1; }
DOCROOT="${JDOCMUNCH_DOCROOT:-${PROJECT}/.doc}"

# Embeddings disabled 2026-11-03: lexical search is more accurate on this
# corpus (see the benchmark in .doc/harnes/mcp/jdocmunch.md). No provider, no
# model cache, no vector sidecar.
export DOC_INDEX_PATH="${DOC_INDEX_PATH:-${HOME}/.doc-index}"

JDOCMUNCH_BIN="${HOME}/.local/bin/jdocmunch-mcp"

IGNORES=(
  --extra-ignore-pattern 'backups/'
  --extra-ignore-pattern 'jsondoc_scripts/'
  --extra-ignore-pattern 'codeception/vendor/'
  --extra-ignore-pattern 'codeception/tests/'
  --extra-ignore-pattern '*.sql'
  --extra-ignore-pattern '*.pdf'
  --extra-ignore-pattern '__pycache__/'
  --extra-ignore-pattern '.content-extractor/'
  --extra-ignore-pattern '.jira/'
  --extra-ignore-pattern '.bitbucket/'
  --extra-ignore-pattern '.mcpyandexscreen/'
)

# Resolve the repo handle from index metadata, never from a hardcoded name.
# Exact source_root wins; otherwise the deepest indexed root inside DOCROOT,
# which covers projects that index a subfolder such as .doc/archiecture.
resolve_repo() {
  JDOCMUNCH_WANT_ROOT="${DOCROOT}" python3 - <<'PY' 2>/dev/null || true
import json, os, sys

base = os.environ.get("DOC_INDEX_PATH") or os.path.join(os.path.expanduser("~"), ".doc-index")
want = os.path.realpath(os.environ["JDOCMUNCH_WANT_ROOT"])
local = os.path.join(base, "local")
if not os.path.isdir(local):
    sys.exit(0)

exact = ""
nested = ""
nested_len = -1
for row in sorted(os.listdir(local)):
    if not row.endswith(".summary.json"):
        continue
    try:
        with open(os.path.join(local, row), encoding="utf-8") as fh:
            summary = json.load(fh)
    except Exception:
        continue
    repo = summary.get("repo") or ""
    root = summary.get("source_root") or ""
    if not repo or not root:
        continue
    real = os.path.realpath(root)
    if real == want:
        exact = repo
        break
    if want == real or want.startswith(real + os.sep):
        if len(real) > nested_len:
            nested, nested_len = repo, len(real)

print(exact or nested)
PY
}

REPO="${JDOCMUNCH_REPO:-}"
if [ -z "${REPO}" ]; then
  REPO="$(resolve_repo)"
fi
if [ -z "${REPO}" ]; then
  REPO="local/$(basename "${PROJECT}")"
fi
NAME="${JDOCMUNCH_INDEX_NAME:-${REPO#*/}}"

# The corpus is a controlled list of directories, not the whole .doc.
# .doc/tasks holds generated run artifacts that duplicate the same knowledge,
# so prune them instead of embedding thousands of copies.
CORPUS_DIRS="${JDOCMUNCH_CORPUS:-architecture harnes tasks web}"
CORPUS_PRUNE=(
  -name test-runs
  -o -name tests
  -o -name reports
  -o -name backups
  -o -name 'backup-*'
  -o -name _jsondoc
  -o -name _dialogs
  -o -name dialogs
  -o -name business-rules
  -o -name technical-facts
  -o -name ui-rules
)

# Build the explicit path list for one index run. `--paths-from` skips the
# directory walk, so every exclusion has to be applied here.
build_paths_file() {
  local tmp dir
  tmp="$(mktemp "${TMPDIR:-/tmp}/jdocmunch-paths.XXXXXX")"
  for dir in ${CORPUS_DIRS}; do
    [ -d "${DOCROOT}/${dir}" ] || continue
    find "${DOCROOT}/${dir}" \
      -type d \( "${CORPUS_PRUNE[@]}" \) -prune -o \
      -type f -name '*.md' -print >> "${tmp}"
  done
  echo "${tmp}"
}

if [ "${1:-}" = "--corpus" ]; then
  PATHS_FILE="$(build_paths_file)"
  wc -l < "${PATHS_FILE}" | tr -d ' '
  rm -f "${PATHS_FILE}"
  exit 0
fi

if [ "${1:-}" = "--index" ]; then
  shift
  PATHS_FILE="$(build_paths_file)"
  set +e
  "${JDOCMUNCH_BIN}" index-local \
    --path "${DOCROOT}" \
    --name "${NAME}" \
    --paths-from "${PATHS_FILE}" \
    --embeddings off \
    "${IGNORES[@]}" \
    "$@"
  status=$?
  set -e
  rm -f "${PATHS_FILE}"
  exit "${status}"
fi

# Print the handle agents must pass as `repo` in every search_sections call.
if [ "${1:-}" = "--repo" ]; then
  echo "${REPO}"
  exit 0
fi

# What is indexed, on which model, and whether vectors are present.
if [ "${1:-}" = "--status" ]; then
  JDOCMUNCH_MARK_REPO="${REPO}" python3 - <<'PY'
import json, os

base = os.environ.get("DOC_INDEX_PATH") or os.path.join(os.path.expanduser("~"), ".doc-index")
mine = os.environ.get("JDOCMUNCH_MARK_REPO") or "-"
local = os.path.join(base, "local")
for row in sorted(os.listdir(local)) if os.path.isdir(local) else []:
    if not row.endswith(".summary.json"):
        continue
    stem = row[: -len(".summary.json")]
    with open(os.path.join(local, row), encoding="utf-8") as fh:
        summary = json.load(fh)
    emb = os.path.join(local, stem + ".embeddings.jsonl")
    model = "-"
    if os.path.exists(emb):
        with open(emb, encoding="utf-8") as fh:
            model = json.loads(fh.readline()).get("model", "-")
    mark = "<-- this project" if summary.get("repo") == mine else ""
    print(f"{summary.get('repo'):24} sections={summary.get('section_count'):<6} "
          f"docs={summary.get('doc_count'):<5} model={model} {mark}")
PY
  exit 0
fi

# MCP clients run: bash <this script> serve
exec "${JDOCMUNCH_BIN}" "$@"
