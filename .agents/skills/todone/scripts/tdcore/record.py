"""Запись задачи как объект: один файл `task.json` — один дом записи."""

import datetime
import json
import os

from . import schema
from .errors import Issue, SkillError


def now_stamp():
    """Метка времени в UTC, секунды, формат ISO 8601 с Z."""
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


def today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class Record:
    """Запись: данные, путь к файлу и папке, составные части и размеры.

    Запись не знает про очередь и про индекс: она отвечает только за свой файл.
    """

    __slots__ = ("data", "path", "folder")

    def __init__(self, data, path=None, folder=None):
        self.data = data
        self.path = path
        self.folder = folder or (os.path.dirname(path) if path else None)

    # --- идентификация ---
    @property
    def id(self):
        return self.data.get("id")

    @property
    def kind(self):
        """Тип записи: ключ `kind`, неизменен после создания."""
        return self.data.get("kind")

    @property
    def status(self):
        return self.data.get("status")

    @property
    def title(self):
        return self.data.get("title") or ""

    @property
    def parent(self):
        return self.data.get("parent")

    @property
    def is_mirror(self):
        return self.kind == "mirror" or self.status == "mirror"

    # --- составные части ---
    @property
    def extra(self):
        return self.data.setdefault("extra", {})

    @property
    def refs(self):
        return self.data.setdefault("refs", [])

    @property
    def artifacts(self):
        return self.data.setdefault("artifacts", [])

    @property
    def comments(self):
        return self.data.setdefault("comments", [])

    @property
    def source(self):
        return self.data.get("source")

    # --- адреса элементов ---
    def elements(self, field):
        """Массив элементов {"id", "text"} поля записи."""
        items = self.data.get(field) or []
        return [el for el in items if isinstance(el, dict)]

    def element(self, address):
        """Элемент по адресу, например `AC-2`. Адрес без поля ищется везде."""
        for field in schema.ELEMENT_FIELDS:
            for el in self.elements(field):
                if el.get("id") == address:
                    return field, el
        return None, None

    def comment(self, comment_id):
        for el in self.comments:
            if isinstance(el, dict) and el.get("id") == comment_id:
                return el
        return None

    # --- лента ---
    def add_comment(self, text, by, kind="agent", at=None):
        """Реплика в ленту. Идентификатор назначается по числу реплик."""
        if not isinstance(text, str) or not text.strip():
            raise SkillError("EMPTY", "текст реплики обязателен и не может быть пустым",
                             "%s comments" % self.id)
        if kind not in schema.COMMENT_KINDS:
            raise SkillError("STATUS_UNKNOWN",
                             "род реплики «%s» не из %s"
                             % (kind, list(schema.COMMENT_KINDS)),
                             "%s comments" % self.id,
                             hint="род реплики — %s"
                                  % ", ".join(schema.COMMENT_KINDS))
        number = len([c for c in self.comments if isinstance(c, dict)]) + 1
        item = {"id": "C-%d" % number, "at": at or now_stamp(), "by": by,
                "kind": kind, "text": text}
        self.comments.append(item)
        return item

    def handoffs(self):
        return [c for c in self.comments
                if isinstance(c, dict) and c.get("kind") == "handoff"]

    def tail(self, last):
        """Хвост ленты: последние K реплик плюс все реплики пересменки.

        Отбор реплик — не усечение текста: каждая отдаётся дословно.
        """
        items = [c for c in self.comments if isinstance(c, dict)]
        picked = items[-last:] if last and last > 0 else list(items)
        for item in items:
            if item.get("kind") == "handoff" and item not in picked:
                picked.append(item)
        picked_set = {id(item) for item in picked}
        picked = [item for item in items if id(item) in picked_set]
        return picked, len(items) - len(picked)

    # --- указатели и артефакты ---
    def add_ref(self, kind, path, note, symbol=None, lines=None, found_by=None,
                by=None):
        if not note or not str(note).strip():
            raise SkillError("REF_NOTE_MISSING",
                             "указатель без пояснения: непонятно, что в нём смотреть",
                             "%s refs" % self.id)
        if kind not in schema.REF_KINDS:
            raise SkillError("KEY_UNKNOWN",
                             "род указателя «%s» не из %s" % (kind, list(schema.REF_KINDS)),
                             "%s refs" % self.id)
        item = {"kind": kind, "path": path, "symbol": symbol, "lines": lines,
                "note": note, "found_by": found_by}
        self.refs.append(item)
        if by:
            self.add_comment("указатель %s %s: %s" % (kind, path, note), by,
                             kind="agent")
        return item

    def add_artifact(self, kind, path, note, derived=False, by=None):
        if kind not in schema.ARTEFACT_KINDS:
            raise SkillError("KEY_UNKNOWN",
                             "род артефакта «%s» не из %s" % (kind, list(schema.ARTEFACT_KINDS)),
                             "%s artifacts" % self.id)
        if ".." in path.split("/") or path.startswith("/"):
            raise SkillError("PATH_OUTSIDE",
                             "путь артефакта «%s» ведёт за пределы папки записи" % path,
                             "%s artifacts" % self.id)
        item = {"kind": kind, "derived": bool(derived), "path": path,
                "note": note}
        self.artifacts.append(item)
        if by:
            self.add_comment("артефакт %s %s: %s" % (kind, path, note), by,
                             kind="agent")
        return item

    def rename_pointer(self, table, old, new, note, by):
        """Переименование указателя или артефакта: след остаётся в ленте."""
        found = None
        for item in table:
            if isinstance(item, dict) and item.get("path") == old:
                found = item
                break
        if found is None:
            raise SkillError("RECORD_NOT_FOUND",
                             "указателя «%s» в записи нет" % old, self.id)
        if not note or not str(note).strip():
            raise SkillError("EMPTY",
                             "переименование требует пояснение: что и зачем перенесено",
                             self.id)
        found["path"] = new
        self.add_comment("переименовано: %s → %s (%s)" % (old, new, note), by,
                         kind="agent")
        return found

    # --- размеры ---
    def body_text(self):
        """Тело записи без ленты: то, что отдаёт режим чтения тела."""
        data = {k: v for k, v in self.data.items() if k != "comments"}
        return json.dumps(data, ensure_ascii=False, indent=2)

    def comments_text(self):
        return "\n".join(
            "%s %s %s: %s" % (c.get("id"), c.get("at"), c.get("by"),
                              c.get("text"))
            for c in self.comments if isinstance(c, dict))

    def sizes(self):
        """Размеры в знаках и байтах: факты для строки состояния."""
        body = self.body_text()
        tape = self.comments_text()
        return {
            "body_chars": len(body),
            "body_bytes": len(body.encode("utf-8")),
            "comments_chars": len(tape),
            "comments_bytes": len(tape.encode("utf-8")),
            "comments_count": len([c for c in self.comments if isinstance(c, dict)]),
        }

    def toc_line(self, comment):
        """Строка оглавления реплики: идентификатор, время, автор, род, первая строка."""
        text = str(comment.get("text") or "")
        first = text.split("\n", 1)[0]
        return "%s %s %s %s %d зн. | %s" % (
            comment.get("id"), comment.get("at"), comment.get("by"),
            comment.get("kind"), len(text), first)

    def as_dict(self):
        return dict(self.data)

    def __repr__(self):
        return "Record(%s %s %s)" % (self.id, self.kind, self.status)


def new_task(task_id, title, kind, status="draft", **fields):
    """Собрать запись TASK-6 с полным составом ключей."""
    data = {key: None for key in schema.TASK_KEYS}
    for field in schema.ELEMENT_FIELDS:
        data[field] = []
    data.update({
        "id": task_id, "title": title, "kind": kind, "status": status,
        "priority": 2, "phase": None, "depends_on": [],
        "parallelizable": False, "created_at": now_stamp(),
        "extra": {}, "refs": [], "artifacts": [], "comments": [],
    })
    for key, value in fields.items():
        if key not in schema.TASK_KEYS:
            raise SkillError("KEY_UNKNOWN",
                             "ключа «%s» в схеме TASK-6 нет" % key, task_id)
        data[key] = value
    return data


def validate_task(record, where=None, issues=None, typedef=None, strict=True):
    """Уровень первый: ядро проверяет схему и факты записи.

    Возвращает список находок. Тексты не режет и не меряет: проверяются
    наличие значения, его тип, перечисление и формат.
    """
    issues = issues if issues is not None else []
    data = record.data if isinstance(record, Record) else record
    spot = where or str(data.get("id") or "запись")

    for key in data:
        if key not in schema.TASK_KEYS:
            issues.append(Issue("error", spot, "ключ «%s» не из схемы TASK-6" % key,
                                "KEY_UNKNOWN"))
    for key in ("id", "title", "kind", "status"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(Issue("error", "%s.%s" % (spot, key),
                                "значение обязательно и не может быть пустым", "EMPTY"))
    if data.get("status") not in schema.STATUSES:
        issues.append(Issue("error", "%s.status" % spot,
                            "статус «%s» не из %s" % (data.get("status"),
                                                       list(schema.STATUSES)),
                            "STATUS_UNKNOWN"))
    task_id = data.get("id")
    if isinstance(task_id, str) and not schema.ID_RE.match(task_id):
        issues.append(Issue("error", "%s.id" % spot,
                            "идентификатор «%s» не в форме T-NNN" % task_id,
                            "ID_IMMUTABLE"))
    kind = data.get("kind")
    if isinstance(kind, str) and not schema.TYPE_ID_RE.match(kind):
        issues.append(Issue("error", "%s.kind" % spot,
                            "имя типа «%s» не в форме строчных букв, цифр и дефисов" % kind,
                            "TYPE_UNKNOWN"))

    due = data.get("due")
    if due is not None and not (isinstance(due, str)
                                and schema.DATE_ONLY_RE.match(due)):
        issues.append(Issue("error", "%s.due" % spot,
                            "срок «%s» не в форме ГГГГ-ММ-ДД" % due, "KEY_UNKNOWN"))
    release = data.get("release")
    if release is not None and not (isinstance(release, str)
                                    and schema.RELEASE_RE.match(release)):
        issues.append(Issue("error", "%s.release" % spot,
                            "имя релиза — null либо непустая строка", "RELEASE_FORMAT"))
    estimate = data.get("estimate_h")
    if estimate is not None and not isinstance(estimate, (int, float)):
        issues.append(Issue("error", "%s.estimate_h" % spot,
                            "оценка — число часов либо null", "KEY_UNKNOWN"))
    priority = data.get("priority")
    if priority is not None and not isinstance(priority, int):
        issues.append(Issue("error", "%s.priority" % spot,
                            "приоритет — целое число либо null", "KEY_UNKNOWN"))

    for field, prefix in schema.ELEMENT_FIELDS.items():
        items = data.get(field)
        if items is None:
            continue
        if not isinstance(items, list):
            issues.append(Issue("error", "%s.%s" % (spot, field),
                                "поле должно быть массивом элементов", "KEY_UNKNOWN"))
            continue
        seen = set()
        for pos, el in enumerate(items):
            place = "%s.%s[%d]" % (spot, field, pos)
            if not isinstance(el, dict):
                issues.append(Issue("error", place, "элемент — объект с id и text",
                                    "KEY_UNKNOWN"))
                continue
            for key in el:
                if key not in ("id", "text", "status"):
                    issues.append(Issue("error", place,
                                        "ключ «%s» лишний у элемента" % key,
                                        "KEY_UNKNOWN"))
            el_id = el.get("id")
            if not isinstance(el_id, str) or not el_id.startswith(prefix + "-"):
                issues.append(Issue("error", place,
                                    "идентификатор элемента должен начинаться с %s-" % prefix,
                                    "KEY_UNKNOWN"))
            elif el_id in seen:
                issues.append(Issue("error", place,
                                    "идентификатор %s повторяется" % el_id, "KEY_UNKNOWN"))
            seen.add(el_id)
            text = el.get("text")
            if not isinstance(text, str) or not text.strip():
                issues.append(Issue("error", "%s %s" % (place, el_id or ""),
                                    "текст элемента обязателен и не может быть пустым",
                                    "EMPTY"))

    _validate_refs(record, spot, issues)
    _validate_artifacts(record, spot, issues)
    _validate_comments(record, spot, issues)
    _validate_source(record, spot, issues)
    _validate_documentation_impact(record, spot, issues)
    if strict:
        _validate_acceptance(record, spot, issues, typedef)
    return issues


def _validate_refs(record, spot, issues):
    refs = record.data.get("refs")
    if refs is None:
        return
    if not isinstance(refs, list):
        issues.append(Issue("error", "%s.refs" % spot, "указатели — массив REF-1",
                            "KEY_UNKNOWN"))
        return
    for pos, ref in enumerate(refs):
        place = "%s.refs[%d]" % (spot, pos)
        if not isinstance(ref, dict):
            issues.append(Issue("error", place, "указатель — объект REF-1",
                                "KEY_UNKNOWN"))
            continue
        for key in ref:
            if key not in schema.REF_KEYS:
                issues.append(Issue("error", place, "ключ «%s» не из REF-1" % key,
                                    "KEY_UNKNOWN"))
        if ref.get("kind") not in schema.REF_KINDS:
            issues.append(Issue("error", place,
                                "род указателя «%s» не из %s" % (ref.get("kind"),
                                                                 list(schema.REF_KINDS)),
                                "KEY_UNKNOWN"))
        if not isinstance(ref.get("path"), str) or not ref["path"].strip():
            issues.append(Issue("error", place,
                                "адрес указателя обязателен и не может быть пустым", "EMPTY"))
        note = ref.get("note")
        if not isinstance(note, str) or not note.strip():
            issues.append(Issue("error", place,
                                "указатель без пояснения: непонятно, что в нём смотреть",
                                "REF_NOTE_MISSING"))


def _validate_artifacts(record, spot, issues):
    arts = record.data.get("artifacts")
    if arts is None:
        return
    if not isinstance(arts, list):
        issues.append(Issue("error", "%s.artifacts" % spot,
                            "артефакты — массив ARTEFACT-1", "KEY_UNKNOWN"))
        return
    for pos, art in enumerate(arts):
        place = "%s.artifacts[%d]" % (spot, pos)
        if not isinstance(art, dict):
            issues.append(Issue("error", place, "артефакт — объект ARTEFACT-1",
                                "KEY_UNKNOWN"))
            continue
        for key in art:
            if key not in schema.ARTEFACT_KEYS:
                issues.append(Issue("error", place,
                                    "ключ «%s» не из ARTEFACT-1" % key, "KEY_UNKNOWN"))
        if art.get("kind") not in schema.ARTEFACT_KINDS:
            issues.append(Issue("error", place,
                                "род артефакта «%s» не из %s" % (art.get("kind"),
                                                                 list(schema.ARTEFACT_KINDS)),
                                "KEY_UNKNOWN"))
        path = art.get("path")
        if not isinstance(path, str) or not path.strip():
            issues.append(Issue("error", place,
                                "путь артефакта обязателен и не может быть пустым", "EMPTY"))
        elif path.startswith("/") or ".." in path.split("/"):
            issues.append(Issue("error", place,
                                "путь «%s» ведёт за пределы папки записи" % path,
                                "PATH_OUTSIDE"))
        if not isinstance(art.get("note"), str) or not art["note"].strip():
            issues.append(Issue("error", place,
                                "у артефакта нет пояснения, что внутри", "EMPTY"))
        if record.folder and isinstance(path, str) and path.strip():
            full = os.path.join(record.folder, path)
            if not os.path.exists(full):
                issues.append(Issue("error", place,
                                    "файла артефакта «%s» в папке записи нет" % path,
                                    "ARTIFACT_MISSING"))


def _validate_comments(record, spot, issues):
    items = record.data.get("comments")
    if items is None:
        return
    if not isinstance(items, list):
        issues.append(Issue("error", "%s.comments" % spot, "лента — массив COMMENT-1",
                            "KEY_UNKNOWN"))
        return
    seen = set()
    for pos, el in enumerate(items):
        place = "%s.comments[%d]" % (spot, pos)
        if not isinstance(el, dict):
            issues.append(Issue("error", place, "реплика — объект COMMENT-1",
                                "KEY_UNKNOWN"))
            continue
        for key in el:
            if key not in schema.COMMENT_KEYS:
                issues.append(Issue("error", place,
                                    "ключ «%s» не из COMMENT-1" % key, "KEY_UNKNOWN"))
        cid = el.get("id")
        if not isinstance(cid, str) or not cid.startswith("C-"):
            issues.append(Issue("error", place,
                                "идентификатор реплики должен начинаться с C-",
                                "KEY_UNKNOWN"))
        elif cid in seen:
            issues.append(Issue("error", place,
                                "идентификатор реплики %s повторяется" % cid,
                                "KEY_UNKNOWN"))
        seen.add(cid)
        if el.get("kind") not in schema.COMMENT_KINDS:
            issues.append(Issue("error", place,
                                "род реплики «%s» не из %s" % (el.get("kind"),
                                                               list(schema.COMMENT_KINDS)),
                                "KEY_UNKNOWN"))
        text = el.get("text")
        if not isinstance(text, str) or not text.strip():
            issues.append(Issue("error", place,
                                "текст реплики обязателен и не может быть пустым", "EMPTY"))
        if not isinstance(el.get("by"), str) or not el["by"].strip():
            issues.append(Issue("error", place,
                                "у реплики не назван автор", "EMPTY"))


def _validate_documentation_impact(record, spot, issues):
    impact = record.data.get("documentation_impact")
    if impact is None:
        return
    place = "%s.documentation_impact" % spot
    if not isinstance(impact, dict):
        issues.append(Issue("error", place, "documentation_impact — объект",
                            "DOC_IMPACT_INVALID"))
        return
    for key in impact:
        if key not in schema.DOC_IMPACT_KEYS:
            issues.append(Issue("error", "%s.%s" % (place, key),
                                "ключ не из documentation_impact", "DOC_IMPACT_INVALID"))
    mode = impact.get("mode")
    if mode not in schema.DOC_IMPACT_MODES:
        issues.append(Issue("error", "%s.mode" % place,
                            "mode должен быть одним из %s" % list(schema.DOC_IMPACT_MODES),
                            "DOC_IMPACT_INVALID"))
    if mode == "none" and not isinstance(impact.get("reason"), str):
        issues.append(Issue("error", "%s.reason" % place,
                            "mode=none требует reason", "DOC_IMPACT_INVALID"))
    if "doc_keys" in impact and (not isinstance(impact.get("doc_keys"), list)
                                  or not all(isinstance(item, str) for item in impact["doc_keys"])):
        issues.append(Issue("error", "%s.doc_keys" % place,
                            "doc_keys — массив строк", "DOC_IMPACT_INVALID"))
    for key, values in (("cadence", schema.POLICY_CADENCE),
                        ("update_after", schema.POLICY_UPDATE_AFTER),
                        ("verify", schema.POLICY_VERIFY),
                        ("automation_override", schema.POLICY_AUTOMATION),
                        ("enforcement_override", schema.POLICY_ENFORCEMENT)):
        if impact.get(key) is not None and impact[key] not in values:
            issues.append(Issue("error", "%s.%s" % (place, key),
                                "значение не из %s" % list(values), "DOC_IMPACT_INVALID"))


def _validate_source(record, spot, issues):
    src = record.data.get("source")
    if src is None:
        if record.kind == "mirror":
            issues.append(Issue("error", "%s.source" % spot,
                                "у зеркала нет источника: загрузка обязана хранить содержимое",
                                "SOURCE_RAW_MISSING"))
        return
    if not isinstance(src, dict):
        issues.append(Issue("error", "%s.source" % spot, "источник — объект SRC-2",
                            "KEY_UNKNOWN"))
        return
    for key in src:
        if key not in schema.SRC_KEYS:
            issues.append(Issue("error", "%s.source" % spot,
                                "ключ «%s» лишний: схема SRC-2 строга" % key,
                                "SOURCE_KEYS_EXTRA"))
    for key in schema.SRC_REQUIRED:
        if not isinstance(src.get(key), str) or not src[key].strip():
            issues.append(Issue("error", "%s.source.%s" % (spot, key),
                                "значение обязательно и не может быть пустым", "EMPTY"))
    if src.get("system") not in schema.SRC_SYSTEMS:
        issues.append(Issue("error", "%s.source.system" % spot,
                            "система «%s» не из %s" % (src.get("system"),
                                                       list(schema.SRC_SYSTEMS)),
                            "KEY_UNKNOWN"))
    raw = src.get("raw")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        issues.append(Issue("error", "%s.source.raw" % spot,
                            "содержимое источника обязательно: зеркало хранит вход дословно",
                            "SOURCE_RAW_MISSING"))
    revision = src.get("revision")
    if revision is not None and not isinstance(revision, int):
        issues.append(Issue("error", "%s.source.revision" % spot,
                            "ревизия — целое число", "KEY_UNKNOWN"))


def _validate_acceptance(record, spot, issues, typedef):
    """Минимум два критерия приёмки: это проверяемость, а не длина."""
    gates = {}
    if typedef is not None:
        gates = typedef.gates or {}
    if gates.get("acceptance_min") is False:
        return
    items = record.data.get("acceptance") or []
    items = [el for el in items if isinstance(el, dict)]
    minimum = gates.get("acceptance_min") or 2
    if record.status not in ("draft",) and len(items) < minimum:
        issues.append(Issue("warning", "%s.acceptance" % spot,
                            "критериев приёмки %d, нужно не меньше %d: задача непроверяема"
                            % (len(items), minimum), "AC_TOO_FEW"))
