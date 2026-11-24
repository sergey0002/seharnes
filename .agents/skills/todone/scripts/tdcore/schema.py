"""Схемы данных очереди: TASK-6, INDEX-1, REF-1, ARTEFACT-1, SRC-2, COMMENT-1, REPORT.

Один дом для состава ключей и проверок фактов. Числовых критериев к текстам
здесь нет вовсе: проверяются наличие значения, его тип, перечисление и формат.
"""

import re

#: Ключи записи TASK-6: тело, source/comments/report и составные части.
TODO_KEYS = (
    "id", "title", "priority", "phase", "status", "parent", "depends_on",
    "parallelizable", "module", "problem", "goals", "acceptance", "in_scope",
    "out_of_scope", "context", "files_hint", "steps", "verify",
    "open_questions", "owner", "started_at", "blocked_reason", "notes",
    "change_kind", "created_at", "due", "estimate_h", "kind", "release",
    "source", "comments", "report", "documentation_impact",
)
TASK_EXTRA_KEYS = ("extra", "refs", "artifacts")
TASK_KEYS = TODO_KEYS + TASK_EXTRA_KEYS

#: Статусов восемь. `mirror` в порядке очереди не участвует.
STATUSES = ("draft", "ready", "in_progress", "blocked", "parked", "mirror",
            "closed", "cancelled")
QUEUE_STATUSES = tuple(s for s in STATUSES if s != "mirror")

#: Ключи строки индекса INDEX-1.
#:
#: `flow_run`, `flow_item` и `flow_revision` — производные координаты
#: конкретного запуска/экземпляра логического шага. Они не дублируются в
#: task.json: запись остаётся фактом работы, а состояние маршрута живёт здесь.
INDEX_KEYS = ("schema", "alias", "updated_at", "order", "items")
INDEX_ITEM_KEYS = ("id", "path", "type", "title", "status", "priority", "phase",
                   "release", "owner", "due", "estimate_h", "parent", "flow",
                   "flow_step", "flow_run", "flow_item", "flow_revision",
                   "flow_run_status", "flow_transition", "flow_control",
                   "updated_at")
INDEX_ORDER = "priority -> phase -> id"

#: Ключи указателя REF-1. Пояснение обязательно.
REF_KEYS = ("kind", "path", "symbol", "lines", "note", "found_by")
REF_KINDS = ("file", "symbol", "doc", "url", "queue", "report")

#: Ключи артефакта ARTEFACT-1.
ARTEFACT_KEYS = ("kind", "derived", "path", "note")
ARTEFACT_KINDS = ("spec", "refs", "tests", "report", "log", "digest", "other")

#: Ключи источника SRC-2: содержимое дословно в ключе `raw`.
SRC_KEYS = ("system", "id", "url", "imported_at", "by", "raw", "revision")
SRC_REQUIRED = ("system", "id")
SRC_SYSTEMS = ("jira", "openspec", "speckit", "chat", "file")

#: Ключи реплики ленты COMMENT-1 и её роды.
COMMENT_KEYS = ("id", "at", "by", "kind", "text", "external_id", "question",
                "resolution", "resolved_by", "resolved_at")
COMMENT_KINDS = ("human", "agent", "import", "proposal", "handoff")

#: Ключи отчёта закрытия REPORT.
REPORT_KEYS = (
    "id", "task", "children", "result", "implementation", "files_changed",
    "algorithm", "verification", "evidence", "acceptance_status", "attempts",
    "deviations", "remaining_risks", "events", "completed_at", "completed_by",
)

#: Поля записи, содержащие массив элементов {"id": "<PREFIX>-N", "text": "..."}.
ELEMENT_FIELDS = {
    "goals": "G", "acceptance": "AC", "in_scope": "IN", "out_of_scope": "OUT",
    "context": "CT", "files_hint": "F", "steps": "S", "verify": "V",
    "open_questions": "Q", "notes": "N",
}
REPORT_ELEMENT_FIELDS = {
    "files_changed": "F", "algorithm": "S", "verification": "V",
    "deviations": "DEV", "remaining_risks": "R",
}
AC_STATUSES = ("met", "not_met", "blocked")
STATUS_ELEMENT_FIELDS = {"acceptance_status": AC_STATUSES}

#: Ключи типа TYPE-5: 12 существующих плюс шесть новых.
TYPE_KEYS = (
    "id", "name", "default", "class", "owner_default", "phase_default",
    "change_kind_default", "executor", "stages", "gates", "uses", "template",
)
TYPE_PLUGIN_KEYS = ("fields", "capabilities", "checks", "editor", "profile")
EDITORS = ("any", "import_only")
CAPABILITIES = ("code-graph", "memory", "web-search", "git", "test-runner",
                "docs-store")
CLASSES = ("product", "research", "source")
TIERS = ("cheap", "balanced", "strong")
MODES = ("subagent", "inline", "either")

#: Ключи объявления дополнительного поля FIELD-1. Числовых критериев нет.
FIELD_KEYS = ("name", "type", "required", "enum", "pattern", "message",
              "example")
FIELD_TYPES = ("string", "int", "number", "bool", "array", "object")

#: Ключи проверки CHECK-1 и её кода CODE-1.
CHECK_KEYS = ("id", "module", "class", "when", "codes")
CHECK_WHEN = ("on_close", "on_evidence", "on_demand")
CODE_KEYS = ("id", "level", "hint")
CODE_LEVELS = ("error", "warning")

#: Ключи потока FLOW-1/FLOW-2 и declarative choice/control extensions.
#:
#: Новые поля остаются optional: старые FLOW-1/FLOW-2 definitions не меняют
#: поведение и проходят тот же validator.  Если extension объявлена, её
#: собственный validator делает контракт строгим.
FLOW_KEYS = ("id", "name", "entry", "steps", "max_batch", "instruction",
             "schema", "version", "allowlist", "allowlisted", "presets",
             "entry_selection", "choice", "decision_tree", "transitions",
             "policy", "release", "capabilities")
FLOW_ENTRIES = ("source", "file", "text")
STEP_KEYS = ("id", "type", "input_from", "output", "outputs", "executor",
             "parallel", "optional", "gate_out", "brief", "requires", "routes",
             "route_field", "fan_out", "step_control", "documentation",
             "choice", "decision_tree", "version")
FAN_OUT_KEYS = ("items_from", "item_id", "task_type_from", "title_from", "join")
JOIN_MODES = ("all_closed",)

#: FLOW-2 control/choice/policy enumerations.
CHOICE_SELECTIONS = ("boolean", "single", "multiple", "text")
POLICY_AUTOMATION = ("ask", "always", "manual", "disabled")
POLICY_ENFORCEMENT = ("advisory", "required", "critical")
POLICY_CADENCE = ("slice", "aggregate", "both", "explicit")
POLICY_UPDATE_AFTER = ("implementation", "slice_tests", "all_tests", "explicit_command")
POLICY_VERIFY = ("on_update", "after_final_tests", "on_close")
FLOW_CONTROL_ROUTES = ("block", "skip_with_reason", "route", "cancel", "manual_only")
FLOW_POLICY_SCOPES = ("step", "flow_run", "change", "workspace", "task")
TRANSITION_STATUSES = ("requested", "approved", "applied", "blocked", "rejected")

#: Exact machine envelope key registries exposed by ``tcheck schema``.
FLOW_CHOICE_KEYS = ("$schema", "schema", "request_id", "flow_run", "task_ref",
                    "decision_id", "question", "selection", "options", "default",
                    "allow_custom_response", "policy_scope", "expires_at", "flow_id",
                    "flow_revision", "step_id", "version",
                    "source", "metadata")
FLOW_STEP_CONTROL_KEYS = ("schema", "enabled_by_default", "confirmation", "question",
                          "on_decline", "on_disabled", "policy_key", "scope")
FLOW_TRANSITION_KEYS = ("schema", "transition_id", "from_flow", "from_run", "from_step",
                        "transition", "target_flow", "target_step", "choice_ref",
                        "carry_refs", "requested_by", "status", "scope",
                        "release_context", "policy", "created_at", "approved_at",
                        "applied_at", "new_run", "new_record", "reason", "validation",
                        "parent_transition")
DOC_POLICY_KEYS = ("policy", "automation", "enforcement", "cadence", "update_after",
                   "verify", "render", "audit", "updated_at", "updated_by", "reason", "mode")
DOC_MODULE_KEYS = ("$schema", "schema", "workspace_id", "doc_key", "doc_kind",
                   "canonical_path", "machine_path", "claims_path", "revision", "status",
                   "summary", "audience", "scope", "content_format", "machine_format",
                   "source_task_refs", "source_refs", "source_fingerprints", "supersedes",
                   "created_at", "updated_at", "updated_by", "generated", "checks")
DOC_IMPACT_KEYS = ("mode", "doc_keys", "reason", "cadence", "update_after",
                   "verify", "automation_override", "enforcement_override", "policy_reason")
DOC_IMPACT_MODES = ("none", "update", "create", "retire")
FLOW_DOC_KEYS = ("schema", "policy_key", "required", "confirmation", "question",
                 "on_decline", "on_disabled", "automation", "cadence", "update_after", "verify",
                 "enforcement", "retain_impact_record")
DOC_CAPTURE_KEYS = ("$schema", "schema", "capture_id", "source", "task_refs", "doc_keys",
                    "release_context", "user_intent", "changed_files", "decision_digest",
                    "transcript_digest", "redaction", "provenance", "status")
DOC_MACHINE_KEYS = ("$schema", "schema", "doc_key", "doc_kind", "revision", "profile",
                    "payload", "source_refs", "claim_refs", "extensions")
DOC_CLAIM_KEYS = ("$schema", "schema", "doc_key", "revision", "claims")
DOC_PACKET_KEYS = ("$schema", "schema", "packet_id", "workspace_id", "release_context",
                   "purpose", "task_refs", "doc_keys", "changed_files", "changed_symbols",
                   "selected_modules", "claims", "refs", "test_map", "decision_digest",
                   "limits", "truncation", "unknowns", "conflicts", "stale")
DOC_QUERY_KEYS = ("schema", "mode", "workspace_id", "task_refs", "release_context", "files",
                  "symbols", "doc_keys", "limits", "include_history")
DOC_WRITER_KEYS = ("schema", "docs_changed", "doc_keys", "revisions", "claims_changed",
                   "source_refs", "render_check", "schema_check", "stale_check", "verdict",
                   "unknowns", "next_action")

#: Ключи привязки возможности TOOLS-1, роли ROLE-1, субагента AGENT-1.
TOOL_KEYS = ("capability", "command", "note")
ROLE_KEYS = ("role", "tier", "mode", "tools", "models")
ROLE_REQUIRED = ("role", "tier", "mode", "models")
AGENT_REQUIRED = ("name", "role", "return_contract", "brief")
AGENT_KEYS = ("name", "role", "tools", "boundaries", "return_contract",
              "brief")
RETURN_CONTRACT_KEYS = ("fields", "shape", "persist", "pointer")

#: Ключи реестра очередей.
QUEUES_KEYS = ("schema", "updated_at", "queues")
QUEUE_ENTRY_KEYS = ("alias", "path", "updated_at")

ID_RE = re.compile(r"^T-\d{3}$")
REPORT_ID_RE = re.compile(r"^D-\d{3}$")
TYPE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RELEASE_RE = re.compile(r"^[^\s].*$")
FLOW_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Пороги, которые живуть в настройке проекта, а не в коде как предел текста.
DEFAULT_SETTINGS = {
    "adaptive_comments": 10,
    "adaptive_chars": 8000,
    "digest_chars": 40000,
    "handoff_last": 3,
    "toc_chars": 4000,
    "flow_max_batch": 5,
}
SETTINGS_KEYS = tuple(DEFAULT_SETTINGS)
