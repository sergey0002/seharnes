"""Persistent conversational task-intake and read-only task audit.

The conversational model decides what to ask and when to finalize.  This module
only enforces durable data-integrity rules: versioned envelopes, provenance,
explicit write intent, one open question at a time, typed task creation and an
explicit audit verdict.  Proposed discussion is never silently promoted to a
normative task field.
"""

import copy
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone

from .errors import Issue, SkillError
from .record import now_stamp
from .typedefs import TypeIndex
from .validate import Validator

INTAKE_SCHEMA = "INTAKE-1"
AUDIT_SCHEMA = "TASK-AUDIT-1"
INTAKE_KEYS = (
    "$schema", "schema", "session_id", "trigger", "state", "root", "queue",
    "actor", "created_at", "updated_at", "draft_task_ref", "entries", "questions",
    "answers", "options", "decisions", "risks", "remaining_questions",
    "provenance", "history", "verdict", "finalized_task_ref", "audit_ref",
)
AUDIT_KEYS = (
    "$schema", "schema", "audit_id", "target_ref", "root", "queue", "created_at",
    "updated_at", "actor", "mode", "verdict", "findings", "remaining_questions",
    "remaining_risks", "refs_checked", "code_checked", "task_checked", "docs_checked",
    "provenance", "audit_task_ref",
)
STATE_VALUES = ("ready", "collecting", "draft", "ready_to_finalize", "finalized", "cancelled")
ENTRY_STATUSES = ("observed", "requested", "proposed", "accepted", "unknown", "evidence", "decision")
SOURCE_KINDS = ("message", "file", "screenshot", "url", "task", "code", "document", "decision")
VERDICTS = ("ready", "accepted_with_risks", "approved", "changes_required", "blocked")
_SAFE_SESSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,96}$")


def _sha256_bytes(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_text(value):
    return _sha256_bytes(str(value).encode("utf-8"))


def _read_bytes(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path, value):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _safe_session(session_id):
    if not isinstance(session_id, str) or not _SAFE_SESSION.match(session_id):
        raise SkillError("INTAKE_SESSION_INVALID", "session_id имеет небезопасный формат",
                         str(session_id), command="tcheck intake start --title <название>")
    return session_id


def _list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _elements(values, prefix):
    result = []
    for pos, value in enumerate(_list(values), start=1):
        if isinstance(value, dict):
            text = str(value.get("text") or "").strip()
            item = dict(value)
            item.setdefault("id", "%s-%d" % (prefix, pos))
            item["text"] = text
        else:
            item = {"id": "%s-%d" % (prefix, pos), "text": str(value)}
        if item.get("text"):
            result.append(item)
    return result


def _provenance(source_kind, source_ref, text=None, actor=None, captured_at=None,
                digest=None):
    if source_kind not in SOURCE_KINDS:
        raise SkillError("INTAKE_SOURCE_INVALID", "source_kind не поддержан: %s" % source_kind,
                         source_kind)
    if not source_ref or not str(source_ref).strip():
        raise SkillError("INTAKE_PROVENANCE_MISSING", "для входа нужен source_ref", source_kind)
    return {
        "source_kind": source_kind,
        "source_ref": str(source_ref),
        "digest": digest or (_sha256_text(text) if text is not None else None),
        "actor": actor or "local",
        "captured_at": captured_at or _iso_now(),
    }


def validate_intake_draft(payload, where="intake draft"):
    if not isinstance(payload, dict):
        return [Issue("error", where, "INTAKE-1 должен быть object", "INTAKE_INVALID")]
    issues = []
    for key in payload:
        if key not in INTAKE_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из INTAKE-1", "INTAKE_INVALID"))
    for key in ("schema", "session_id", "trigger", "state", "root", "created_at", "updated_at",
                "entries", "questions", "answers", "options", "decisions", "risks",
                "remaining_questions", "provenance", "history"):
        if key not in payload:
            issues.append(Issue("error", where, "нет обязательного поля «%s»" % key,
                                "INTAKE_INVALID"))
    if payload.get("schema") != INTAKE_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть INTAKE-1", "INTAKE_INVALID"))
    if payload.get("state") not in STATE_VALUES:
        issues.append(Issue("error", "%s.state" % where, "state не из %s" % list(STATE_VALUES),
                            "INTAKE_INVALID"))
    for key in ("entries", "questions", "answers", "options", "decisions", "risks",
                "remaining_questions", "provenance", "history"):
        if key in payload and not isinstance(payload[key], list):
            issues.append(Issue("error", "%s.%s" % (where, key), "поле должно быть array",
                                "INTAKE_INVALID"))
    for pos, item in enumerate(payload.get("provenance") or []):
        if not isinstance(item, dict) or item.get("source_kind") not in SOURCE_KINDS \
                or not item.get("source_ref"):
            issues.append(Issue("error", "%s.provenance[%d]" % (where, pos),
                                "provenance требует source_kind и source_ref",
                                "INTAKE_PROVENANCE_MISSING"))
    open_questions = [item for item in payload.get("questions") or []
                      if isinstance(item, dict) and item.get("status") == "open"]
    if len(open_questions) > 1:
        issues.append(Issue("error", "%s.questions" % where,
                            "одновременно разрешён только один открытый вопрос",
                            "INTAKE_QUESTION_SEQUENCE"))
    return issues


def validate_audit(payload, where="task audit"):
    if not isinstance(payload, dict):
        return [Issue("error", where, "TASK-AUDIT-1 должен быть object", "AUDIT_INVALID")]
    issues = []
    for key in payload:
        if key not in AUDIT_KEYS:
            issues.append(Issue("error", "%s.%s" % (where, key),
                                "ключ не из TASK-AUDIT-1", "AUDIT_INVALID"))
    for key in ("schema", "audit_id", "target_ref", "root", "created_at", "updated_at",
                "mode", "verdict", "findings", "remaining_questions", "remaining_risks",
                "refs_checked", "code_checked", "task_checked", "docs_checked", "provenance"):
        if key not in payload:
            issues.append(Issue("error", where, "нет обязательного поля «%s»" % key,
                                "AUDIT_INVALID"))
    if payload.get("schema") != AUDIT_SCHEMA:
        issues.append(Issue("error", where, "schema должен быть TASK-AUDIT-1", "AUDIT_INVALID"))
    if payload.get("verdict") not in ("approved", "changes_required", "blocked"):
        issues.append(Issue("error", "%s.verdict" % where,
                            "verdict должен быть approved, changes_required или blocked",
                            "AUDIT_INVALID"))
    for key in ("findings", "remaining_questions", "remaining_risks", "provenance"):
        if not isinstance(payload.get(key), list):
            issues.append(Issue("error", "%s.%s" % (where, key), "поле должно быть array",
                                "AUDIT_INVALID"))
    return issues


class DraftStore:
    """Persistent session storage under the project `.todone/intake/` domain."""

    def __init__(self, root, clock=None):
        self.root = os.path.abspath(root)
        self.base = os.path.join(self.root, ".todone", "intake")
        self.clock = clock or _iso_now

    def path(self, session_id):
        return os.path.join(self.base, _safe_session(session_id), "draft.json")

    def events_path(self, session_id):
        return os.path.join(self.base, _safe_session(session_id), "events.jsonl")

    def load(self, session_id):
        path = self.path(session_id)
        if not os.path.isfile(path):
            raise SkillError("INTAKE_SESSION_NOT_FOUND", "intake session не найдена", path,
                             command="tcheck intake list --root <root>")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SkillError("INTAKE_INVALID", "draft не читается: %s" % exc, path)
        issues = validate_intake_draft(payload, path)
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where)
        return IntakeDraft(self, payload)

    def save(self, draft, event=None, actor=None, action=None):
        issues = validate_intake_draft(draft.data, self.path(draft.session_id))
        if any(item.is_error for item in issues):
            first = next(item for item in issues if item.is_error)
            raise SkillError(first.code, first.message, first.where)
        draft.data["updated_at"] = self.clock()
        os.makedirs(os.path.dirname(self.path(draft.session_id)), exist_ok=True)
        if event is not None:
            event_item = {
                "event_id": "E-%04d" % (len(draft.data.get("history") or []) + 1),
                "at": draft.data["updated_at"], "actor": actor or draft.data.get("actor") or "local",
                "action": action or "update", "payload": event,
            }
            draft.data.setdefault("history", []).append(event_item)
            with open(self.events_path(draft.session_id), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event_item, ensure_ascii=False, sort_keys=True) + "\n")
        _atomic_json(self.path(draft.session_id), draft.data)
        return draft

    def start(self, title, actor, queue=None, session_id=None, trigger="постановка задачи"):
        if not title or not str(title).strip():
            raise SkillError("INTAKE_TITLE_MISSING", "для intake нужен краткий заголовок", "title")
        session_id = session_id or "intake-%s" % hashlib.sha256(
            (str(title) + "\n" + (queue or "") + "\n" + (actor or "local")).encode("utf-8")
        ).hexdigest()[:12]
        _safe_session(session_id)
        path = self.path(session_id)
        if os.path.isfile(path):
            return self.load(session_id)
        stamp = self.clock()
        payload = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "schema": INTAKE_SCHEMA, "session_id": session_id,
            "trigger": trigger, "state": "collecting", "root": self.root,
            "queue": queue, "actor": actor or "local", "created_at": stamp,
            "updated_at": stamp, "draft_task_ref": None, "entries": [],
            "questions": [], "answers": [], "options": [], "decisions": [],
            "risks": [], "remaining_questions": [], "provenance": [],
            "history": [], "verdict": None, "finalized_task_ref": None,
            "audit_ref": None,
        }
        draft = IntakeDraft(self, payload)
        self.save(draft, event={"kind": "session_started", "title": title,
                                "trigger": trigger}, actor=actor, action="start")
        draft.add_entry("requested", title, "message", "conversation:start", actor=actor,
                        persist=False)
        self.save(draft, event={"kind": "title", "text": title}, actor=actor, action="capture")
        return draft

    def list(self):
        if not os.path.isdir(self.base):
            return []
        result = []
        for session_id in sorted(os.listdir(self.base)):
            path = self.path(session_id)
            if os.path.isfile(path):
                try:
                    result.append(self.load(session_id).data)
                except SkillError:
                    continue
        return result

    def capture_file(self, draft, path, actor=None, source_kind=None, text=None):
        if not os.path.isfile(path):
            raise SkillError("INTAKE_SOURCE_NOT_FOUND", "входного файла нет: %s" % path, path)
        source_kind = source_kind or ("screenshot" if os.path.splitext(path)[1].lower()
                                      in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "file")
        with open(path, "rb") as handle:
            content = handle.read()
        digest = _sha256_bytes(content)
        safe_name = os.path.basename(path).replace("/", "_").replace("\\", "_")
        destination = os.path.join(self.base, draft.session_id, "inputs", safe_name)
        if os.path.isfile(destination) and _read_bytes(destination) != content:
            stem, extension = os.path.splitext(safe_name)
            safe_name = "%s-%s%s" % (stem, digest[7:19], extension)
            destination = os.path.join(self.base, draft.session_id, "inputs", safe_name)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if not os.path.isfile(destination):
            with open(destination, "wb") as handle:
                handle.write(content)
        ref = os.path.relpath(destination, self.root).replace(os.sep, "/")
        entry = draft.add_entry("observed", text or "Входной файл сохранён как provenance artifact",
                               source_kind, path, actor=actor, digest=digest, persist=False)
        entry["provenance"]["stored_ref"] = ref
        self.save(draft, event={"kind": "file_captured", "source_ref": path,
                                "stored_ref": ref, "digest": digest}, actor=actor,
                  action="capture_file")
        return entry


class IntakeDraft:
    def __init__(self, store, data):
        self.store = store
        self.data = data

    @property
    def session_id(self):
        return self.data["session_id"]

    def _persist(self, event, actor=None, action=None):
        return self.store.save(self, event=event, actor=actor, action=action)

    def add_entry(self, status, text, source_kind, source_ref, actor=None,
                  digest=None, persist=True):
        if status not in ENTRY_STATUSES:
            raise SkillError("INTAKE_ENTRY_STATUS_INVALID", "статус входа неизвестен: %s" % status,
                             status)
        if not text or not str(text).strip():
            raise SkillError("INTAKE_TEXT_MISSING", "intake entry не может быть пустым", self.session_id)
        prov = _provenance(source_kind, source_ref, text=text, actor=actor,
                           captured_at=self.store.clock(), digest=digest)
        entry = {"id": "I-%03d" % (len(self.data["entries"]) + 1),
                 "status": status, "text": str(text), "provenance": prov}
        self.data["entries"].append(entry)
        self.data["provenance"].append(prov)
        if persist:
            self._persist({"kind": "entry", "entry": entry}, actor, "capture")
        return entry

    def add_option(self, label, pros, cons, actor=None, source_ref="conversation:option",
                   persist=True):
        if not label:
            raise SkillError("INTAKE_OPTION_INVALID", "вариант должен иметь label", self.session_id)
        item = {"id": "O-%03d" % (len(self.data["options"]) + 1),
                "label": str(label), "pros": _list(pros), "cons": _list(cons),
                "status": "proposed",
                "provenance": _provenance("message", source_ref, text=label, actor=actor,
                                           captured_at=self.store.clock())}
        self.data["options"].append(item)
        if persist:
            self._persist({"kind": "option", "option": item}, actor, "propose")
        return item

    def accept_option(self, option_id, actor=None, source_ref="conversation:decision", persist=True):
        item = next((item for item in self.data["options"] if item.get("id") == option_id), None)
        if item is None:
            raise SkillError("INTAKE_OPTION_UNKNOWN", "вариант не найден: %s" % option_id, self.session_id)
        for other in self.data["options"]:
            if other.get("status") == "accepted":
                other["status"] = "rejected"
        item["status"] = "accepted"
        decision = {"id": "D-%03d" % (len(self.data["decisions"]) + 1),
                    "option_id": option_id, "actor": actor or "local",
                    "provenance": _provenance("decision", source_ref, text=item["label"],
                                               actor=actor, captured_at=self.store.clock())}
        self.data["decisions"].append(decision)
        if persist:
            self._persist({"kind": "option_accepted", "decision": decision}, actor, "decide")
        return decision

    def ask(self, text, choices=None, default=None, on_decline="ask_again",
            on_disabled="ask_again", actor=None, question_id=None, persist=True):
        open_questions = [item for item in self.data["questions"] if item.get("status") == "open"]
        if open_questions:
            raise SkillError("INTAKE_QUESTION_SEQUENCE",
                             "сначала ответь на текущий вопрос %s" % open_questions[0]["id"],
                             self.session_id)
        choices = _list(choices)
        if default is not None and choices and default not in choices:
            raise SkillError("INTAKE_QUESTION_INVALID", "default отсутствует в choices", self.session_id)
        question = {
            "id": question_id or "Q-%03d" % (len(self.data["questions"]) + 1),
            "text": str(text), "choices": choices, "default": default,
            "on_decline": on_decline, "on_disabled": on_disabled,
            "status": "open", "asked_at": self.store.clock(),
            "provenance": _provenance("decision", "flow:intake", text=text, actor=actor,
                                       captured_at=self.store.clock()),
        }
        self.data["questions"].append(question)
        self.data["remaining_questions"] = [item["id"] for item in self.data["questions"]
                                             if item.get("status") == "open"]
        if persist:
            self._persist({"kind": "question", "question": question}, actor, "ask")
        return question

    def answer(self, question_id, value, actor=None, source="user", disabled=False, persist=True):
        question = next((item for item in self.data["questions"] if item.get("id") == question_id), None)
        if question is None or question.get("status") != "open":
            raise SkillError("INTAKE_QUESTION_UNKNOWN", "открытый вопрос не найден: %s" % question_id,
                             self.session_id)
        if disabled:
            outcome = question.get("on_disabled")
        elif value in (None, "", "decline", "отказ"):
            outcome = question.get("on_decline")
        else:
            outcome = "accepted"
        choices = question.get("choices") or []
        if outcome == "accepted" and choices and value not in choices:
            raise SkillError("INTAKE_ANSWER_INVALID", "ответ отсутствует в choices", question_id)
        answer = {"question_id": question_id, "value": value, "source": source,
                  "outcome": outcome, "actor": actor or "user", "answered_at": self.store.clock(),
                  "provenance": _provenance("decision", "conversation:answer", text=str(value),
                                             actor=actor, captured_at=self.store.clock())}
        question["status"] = "answered"
        question["answer"] = answer
        self.data["answers"].append(answer)
        self.data["remaining_questions"] = [item["id"] for item in self.data["questions"]
                                             if item.get("status") == "open"]
        if persist:
            self._persist({"kind": "answer", "answer": answer}, actor, "answer")
        return answer

    def fix(self, text, source_kind="message", source_ref="conversation:fix",
            actor=None, persist=True):
        """Explicit `зафиксируй в задаче` write: accepted fact, never proposal."""
        entry = self.add_entry("accepted", text, source_kind, source_ref, actor=actor,
                               persist=False)
        if persist:
            self._persist({"kind": "explicit_fix", "entry_id": entry["id"],
                           "intent": "зафиксируй в задаче"}, actor, "explicit_fix")
        return entry

    def report(self):
        remaining = list(self.data.get("remaining_questions") or [])
        risks = list(self.data.get("risks") or [])
        verdict = "ready" if not remaining else "blocked"
        self.data["verdict"] = verdict
        self.data["state"] = "ready_to_finalize" if verdict == "ready" else "collecting"
        return {"session_id": self.session_id, "verdict": verdict,
                "remaining_questions": remaining, "remaining_risks": risks,
                "accepted": [item for item in self.data["entries"] if item.get("status") == "accepted"],
                "proposed": [item for item in self.data["entries"] if item.get("status") == "proposed"]}

    def create_draft_task(self, queue, title=None, actor=None, persist=True):
        """Create the optional operational intake task; caller opted into a write."""
        if self.data.get("draft_task_ref"):
            return queue.resolve(self.data["draft_task_ref"])
        title = title or "Постановка задачи: %s" % self.session_id
        record = queue.create(title, "intake", status="draft", extra={
            "raw_gaps": "сбор требований продолжается",
            "assumptions": "допущения не подтверждены",
            "draft_child": "typed task ещё не сформирован",
        })
        self.data["draft_task_ref"] = record.id
        if persist:
            self._persist({"kind": "draft_task_created", "task_ref": record.id}, actor, "persist_draft")
        return record

    def finalize(self, queue, task_type, title, spec, actor=None, allow_open=False,
                 persist=True, types=None):
        """Validate and create a typed local task only on explicit finalization."""
        report = self.report()
        if report["remaining_questions"] and not allow_open:
            raise SkillError("INTAKE_REQUIRES_CONFIRMATION",
                             "перед финализацией остались вопросы: %s"
                             % ", ".join(report["remaining_questions"]), self.session_id,
                             hint="ответить на вопросы или явно подтвердить remaining risks")
        required = ("problem", "acceptance", "verify")
        missing = [key for key in required if not _list(spec.get(key)) and not str(spec.get(key) or "").strip()]
        if missing:
            raise SkillError("INTAKE_FINALIZE_INCOMPLETE",
                             "для typed task не хватает: %s" % ", ".join(missing), self.session_id)
        types = types or TypeIndex(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "types"))
        if not types.has(task_type):
            raise SkillError("TYPE_UNKNOWN", "тип «%s» не объявлен" % task_type, task_type)
        fields = {"status": "draft", "problem": str(spec.get("problem") or ""),
                  "goals": _elements(spec.get("goals"), "G"),
                  "acceptance": _elements(spec.get("acceptance"), "AC"),
                  "in_scope": _elements(spec.get("in_scope"), "IN"),
                  "out_of_scope": _elements(spec.get("out_of_scope"), "OUT"),
                  "context": _elements(spec.get("context"), "CT"),
                  "files_hint": _elements(spec.get("files_hint"), "F"),
                  "steps": _elements(spec.get("steps"), "S"),
                  "verify": _elements(spec.get("verify"), "V"),
                  "open_questions": _elements(spec.get("open_questions"), "Q"),
                  "change_kind": spec.get("change_kind")}
        record = queue.create(title, task_type, **fields)
        if self.data.get("draft_task_ref"):
            record.add_ref("queue", self.data["draft_task_ref"],
                           "источник требований: persistent intake session %s" % self.session_id)
        record.add_comment("handoff intake %s: verdict=%s; remaining_questions=%s; remaining_risks=%s"
                           % (self.session_id, "accepted_with_risks" if allow_open else "ready",
                              report["remaining_questions"], report["remaining_risks"]),
                           actor or "local", kind="handoff")
        artifact_path = os.path.join(record.folder, "artifacts", "intake.json")
        _atomic_json(artifact_path, self.data)
        record.add_artifact("spec", "artifacts/intake.json",
                            "immutable provenance of conversational intake", derived=False)
        queue.save(record)
        self.data["state"] = "finalized"
        self.data["verdict"] = "accepted_with_risks" if allow_open else "ready"
        self.data["finalized_task_ref"] = record.id
        if persist:
            self._persist({"kind": "finalized", "task_ref": record.id,
                           "verdict": self.data["verdict"]}, actor, "finalize")
        return record

    def audit(self, queue, task_ref, actor=None, persist=True, types=None):
        """Read-only consistency audit with explicit verdict and remaining risks."""
        try:
            target = queue.resolve(task_ref)
        except SkillError as exc:
            raise SkillError("AUDIT_TARGET_NOT_FOUND", exc.message, task_ref)
        types = types or TypeIndex(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "types"))
        issues = Validator(types).record(target, strict=True)
        findings = [item.as_dict() for item in issues]
        refs_checked, code_checked = [], []
        for ref in target.refs:
            if not isinstance(ref, dict):
                continue
            path = str(ref.get("path") or "")
            if ref.get("kind") in ("file", "symbol", "doc"):
                candidate = path if os.path.isabs(path) else os.path.join(self.store.root, path)
                found = os.path.isfile(candidate) or os.path.isdir(candidate)
                refs_checked.append({"ref": ref, "exists": found})
                if not found:
                    findings.append({"level": "error", "where": path,
                                     "message": "ref не разрешается", "code": "AUDIT_REF_BROKEN"})
                if ref.get("kind") == "symbol":
                    code_checked.append({"path": path, "exists": found,
                                         "symbol": ref.get("symbol")})
            elif ref.get("kind") == "queue":
                try:
                    queue.resolve(path)
                    refs_checked.append({"ref": ref, "exists": True})
                except SkillError:
                    refs_checked.append({"ref": ref, "exists": False})
                    findings.append({"level": "error", "where": path,
                                     "message": "queue ref не разрешается", "code": "AUDIT_REF_BROKEN"})
        if not target.data.get("acceptance"):
            findings.append({"level": "error", "where": "%s.acceptance" % target.id,
                             "message": "нет критериев приёмки", "code": "AUDIT_ACCEPTANCE_MISSING"})
        if not target.data.get("verify"):
            findings.append({"level": "error", "where": "%s.verify" % target.id,
                             "message": "нет способа проверки", "code": "AUDIT_VERIFY_MISSING"})
        duplicate_titles = [item.id for item in queue.records
                            if item.id != target.id and item.title == target.title]
        if duplicate_titles:
            findings.append({"level": "warning", "where": target.id,
                             "message": "похожие задачи: %s" % ", ".join(duplicate_titles),
                             "code": "AUDIT_DUPLICATE_CANDIDATE"})
        remaining_questions = [item.get("text") for item in target.elements("open_questions")]
        remaining_risks = list(self.data.get("risks") or [])
        errors = [item for item in findings if item.get("level") == "error"]
        verdict = "blocked" if not target.refs and target.kind in ("feature", "fix", "planning") \
            else ("changes_required" if errors else "approved")
        audit = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "schema": AUDIT_SCHEMA, "audit_id": "audit:%s:%s" % (self.session_id, task_ref),
            "target_ref": task_ref, "root": self.store.root, "queue": queue.alias,
            "created_at": self.store.clock(), "updated_at": self.store.clock(),
            "actor": actor or "local", "mode": "read_only", "verdict": verdict,
            "findings": findings, "remaining_questions": remaining_questions,
            "remaining_risks": remaining_risks, "refs_checked": refs_checked,
            "code_checked": code_checked, "task_checked": {"id": target.id, "kind": target.kind},
            "docs_checked": {"status": "bounded_local_refs_only"},
            "provenance": [{"source_kind": "task", "source_ref": task_ref,
                            "digest": _sha256_text(json.dumps(target.data, sort_keys=True,
                                                               ensure_ascii=False)),
                            "actor": actor or "local", "captured_at": self.store.clock()}],
            "audit_task_ref": None,
        }
        audit_issues = validate_audit(audit)
        if any(item.is_error for item in audit_issues):
            first = next(item for item in audit_issues if item.is_error)
            raise SkillError(first.code, first.message, first.where)
        if persist:
            audit_record = queue.create("Аудит задачи %s" % task_ref, "plan-audit",
                                        status="draft", parent=target.id,
                                        extra={"verdict": verdict,
                                               "findings": json.dumps(findings, ensure_ascii=False,
                                                                       sort_keys=True)})
            audit_record.add_ref("queue", target.id, "исходная задача для read-only аудита")
            audit_record.add_comment("verdict=%s; remaining_questions=%s; remaining_risks=%s"
                                     % (verdict, remaining_questions, remaining_risks),
                                     actor or "local", kind="handoff")
            artifact_path = os.path.join(audit_record.folder, "artifacts", "audit.json")
            _atomic_json(artifact_path, audit)
            audit_record.add_artifact("report", "artifacts/audit.json",
                                      "TASK-AUDIT-1 read-only verdict")
            queue.save(audit_record)
            audit["audit_task_ref"] = audit_record.id
            self.data["audit_ref"] = audit_record.id
            self._persist({"kind": "audit", "audit_task_ref": audit_record.id,
                           "verdict": verdict}, actor, "audit")
        return audit
