"""Точка входа `ttask`: запись как работа.

Состав команд: создать запись, прочитать в выбранном режиме, собрать пакет
субагенту, править поля, переводить статус, брать и освобождать аренду, лента
реплик, указатели, артефакты, свидетельства прогона, отчёт и закрытие, связь
записей указателем, дерево записи, выгрузка для чтения, поток, массовые
операции. Порядок очереди — в `tqueue`, контроль и типы — в `tcheck`.
"""

import json
import os
import shutil
import tempfile

from . import schema
from .brief import Brief
from .cli import Cli, Command
from .digest import PARTS
from .digest import part as digest_part
from .digest import write as digest_write
from .errors import EXIT_FINDINGS, SkillError
from .choice import RESPONSE_SCHEMA
from .documentation import (DocumentationWorkspace, CLAIM_SCHEMA, default_policy,
                            effective_policy, validate_claims)
from .flow import FlowIndex, FlowState
from .gates import close_issues
from .link import link as link_records
from .link import tree as tree_of
from .record import Record, now_stamp
from .report import PACK_MODES, SHOW_MODES, record_line, render_show, render_tree
from .report import sizes_line
from .typedefs import TypeIndex
from .validate import Validator

#: Поля записи, которые правит команда `set` своими флагами.
SET_FIELDS = ("title", "priority", "phase", "release", "owner", "due",
              "module", "problem", "parent", "parallelizable", "change_kind")
#: Рода свидетельства прогона: гейт теста принимает любой из них.
EVIDENCE_KINDS = ("log", "report", "tests")


class TaskCli(Cli):
    """Запись как работа: чтение целиком, правка через CLI, гейты на закрытии."""

    entry = "ttask"
    area = "запись как работа"
    commands = (
        Command("new", "создать запись; --from-text и --from-file создают зеркало",
                flags=[("title", None, "заголовок записи"),
                       ("--type", None, "тип записи из объявленных"),
                       ("--status", None, "начальный статус; по умолчанию draft"),
                       ("--priority", int, "приоритет: целое число"),
                       ("--phase", None, "фаза"),
                       ("--release", None, "релиз"),
                       ("--owner", None, "владелец"),
                       ("--due", None, "срок: ГГГГ-ММ-ДД"),
                       ("--parent", None, "идентификатор родительской записи"),
                       ("--from-text", None,
                        "сырой текст: становится зеркалом дословно"),
                       ("--from-file", None,
                        "файл с сырым текстом: становится зеркалом дословно"),
                       ("--source-system", None,
                        "система источника: %s" % ", ".join(schema.SRC_SYSTEMS)),
                       ("--source-id", None, "идентификатор в системе источника")],
                mutating=True),
        Command("show", "прочитать запись в выбранном режиме: ничего не режется",
                flags=[("address", None,
                        "адрес: T-014, T-014/C-7, T-014/AC-2, D-001"),
                       ("--mode", None,
                        "режим чтения: %s" % ", ".join(SHOW_MODES)),
                       ("--last", int,
                        "сколько последних реплик отдать в режиме handoff")]),
        Command("pack", "пакет субагенту одним вызовом",
                flags=[("address", None, "идентификатор записи"),
                       ("--mode", None,
                        "режим ленты в пакете: %s" % ", ".join(PACK_MODES)),
                       ("--last", int, "сколько последних реплик отдать"),
                       ("--agent", None, "имя субагента из объявления типа")]),
        Command("set", "правка полей: несколько полей и записей за вызов",
                flags=[("ids", None, "идентификаторы записей"),
                       ("--ids", None,
                        "идентификаторы через запятую или «-» из stdin"),
                       ("--title", None, "заголовок"),
                       ("--priority", int, "приоритет"),
                       ("--phase", None, "фаза"),
                       ("--release", None, "релиз"),
                       ("--owner", None, "владелец"),
                       ("--due", None, "срок: ГГГГ-ММ-ДД"),
                       ("--estimate", None, "оценка в часах"),
                       ("--module", None, "модуль"),
                       ("--problem", None, "проблема"),
                       ("--parent", None, "родитель"),
                       ("--depends-on", None, "зависимости через запятую"),
                       ("--change-kind", None, "вид изменения"),
                       ("--goals", None, "цель; флаг повторяется"),
                       ("--acceptance", None, "критерий приёмки; флаг повторяется"),
                       ("--in-scope", None, "в границах; флаг повторяется"),
                       ("--out-of-scope", None, "вне границ; флаг повторяется"),
                       ("--context", None, "контекст; флаг повторяется"),
                       ("--files-hint", None, "подсказка файла; флаг повторяется"),
                       ("--steps", None, "шаг; флаг повторяется"),
                       ("--verify", None, "проверка; флаг повторяется"),
                       ("--open-questions", None, "открытый вопрос; флаг повторяется"),
                       ("--notes", None, "текст поля записи; флаг повторяется"),
                       ("--extra", None,
                        "поле типа: имя=значение; флаг повторяется"),
                       ("--type", None, "тип записи: неизменен после создания"),
                       ("--id", None,
                        "идентификатор: неизменен после создания")],
                mutating=True),
        Command("status", "перевод состояния работы с проверкой гейтов",
                flags=[("ids", None, "идентификаторы записей"),
                       ("--ids", None, "идентификаторы через запятую или «-»"),
                       ("--status", None,
                        "новый статус: %s" % ", ".join(schema.STATUSES)),
                       ("--all", bool, "все записи отбора"),
                       ("--type", None, "отбор по типу записи"),
                       ("--reason", None, "причина перевода: пишется в ленту")],
                mutating=True),
        Command("report-skeleton", "каркас отчёта закрытия в папке записи",
                flags=[("address", None, "идентификатор записи")], mutating=True),
        Command("close", "закрыть запись: гейты типа и отчёт",
                flags=[("address", None, "идентификатор записи"),
                       ("--report", None, "имя файла отчёта в папке записи"),
                       ("--verdict", None,
                        "вердикт по критериям: met, not_met, blocked")],
                mutating=True),
        Command("reopen", "вернуть запись в работу",
                flags=[("address", None, "идентификатор записи"),
                       ("--reason", None, "причина: пишется в ленту")],
                mutating=True),
        Command("claim", "взять запись в работу: владелец и статус",
                flags=[("address", None, "идентификатор записи"),
                       ("--owner", None, "кто берёт; по умолчанию имя из --by")],
                mutating=True),
        Command("unclaim", "освободить аренду записи",
                flags=[("address", None, "идентификатор записи")], mutating=True),
        Command("comment", "лента реплик",
                nested=("add", "list", "brief", "apply", "reject"),
                mutating=True),
        Command("ref", "указатели на файлы, символы, документацию и записи",
                nested=("add", "remove", "rename"), mutating=True),
        Command("artifact", "артефакты в папке записи",
                nested=("add", "remove", "rename"), mutating=True),
        Command("evidence", "свидетельство прогона для гейта типа",
                flags=[("address", None, "идентификатор записи"),
                       ("--kind", None,
                        "род свидетельства: %s" % ", ".join(EVIDENCE_KINDS)),
                       ("--path", None, "путь файла в папке записи"),
                       ("--note", None, "пояснение: что свидетельствует")],
                mutating=True),
        Command("batch", "пакет операций одним вызовом: одна транзакция",
                flags=[("ops", None, "файл операций: массив {op, id, значения}"),
                       ("--dry-run", bool, "напечатать план и ничего не писать")],
                mutating=True),
        Command("link", "связать записи указателем вместо копирования текста",
                flags=[("parent", None, "идентификатор родителя"),
                       ("child", None, "идентификатор ребёнка"),
                       ("--note", None, "пояснение связи: обязательно")],
                mutating=True),
        Command("tree", "дерево записи: потомки, статусы и что каждый оставил",
                flags=[("address", None, "идентификатор записи")]),
        Command("digest", "выгрузка тела и ленты в производный файл для чтения",
                flags=[("address", None, "идентификатор записи"),
                       ("--part", None,
                        "часть выгрузки: %s или comments:N-M" % "|".join(PARTS))],
                mutating=True),
        Command("document", "явный intent «задокументируй»: capture или validated module",
                flags=[("ids", None, "идентификаторы активных задач"),
                       ("--from-chat", None, "готовый DOC-CAPTURE-1 JSON"),
                       ("--doc-key", None, "namespaced ключ модуля"),
                       ("--kind", None, "вид модуля DOC-1; по умолчанию change"),
                       ("--content", None, "Markdown тела модуля"),
                       ("--machine-file", None, "DOC-MACHINE-1 JSON"),
                       ("--claims-file", None, "DOC-CLAIM-1 JSON"),
                       ("--release", None, "release context"),
                       ("--docs-path", None, "workspace write path relative to --root"),
                       ("--changed-file", None, "затронутый файл; флаг повторяется")],
                mutating=True),
        Command("flow", "поток: цепочка черновиков, положение, следующий шаг",
                nested=("start", "state", "next", "choice", "transition"), mutating=True),
    )

    def nested_flags(self, command, action):
        """Флаги вложенных команд: справка называет каждый."""
        return NESTED_FLAGS.get((command, action), [])

    # --- создание ---
    def cmd_new(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        raw = getattr(args, "from_text", None)
        raw_file = getattr(args, "from_file", None)
        if raw is not None or raw_file is not None:
            return self._new_mirror(queue, args, raw, raw_file)
        kind = getattr(args, "type", None) or "default"
        if not types.has(kind):
            raise SkillError("TYPE_UNKNOWN", "тип «%s» не объявлен" % kind,
                             self.paths()["types"], command="tcheck types list")
        fields = _picked(args, ("status", "priority", "phase", "release",
                                "owner", "due", "parent"))
        fields.setdefault("status", "draft")
        record = queue.create(args.title, kind, **fields)
        queue.save(record)
        lines = [record_line(queue.index.find(record.id)),
                 "запись создана: %s" % record.path]
        return self.print_lines(lines, {"id": record.id, "type": kind,
                                        "path": record.path,
                                        "status": record.status},
                                counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    def _new_mirror(self, queue, args, raw, raw_file):
        """Зеркало внешней системы: сырое содержимое дословно внутри записи."""
        text = raw
        origin = "сырой текст"
        system = getattr(args, "source_system", None)
        if raw_file:
            if not os.path.isfile(raw_file):
                raise SkillError("RECORD_NOT_FOUND",
                                 "файла «%s» нет" % raw_file, raw_file,
                                 command="ttask new <заголовок> --from-file <путь>")
            with open(raw_file, "r", encoding="utf-8") as handle:
                text = handle.read()
            origin = raw_file
            system = system or "file"
        system = system or "chat"
        if not text or not text.strip():
            raise SkillError("SOURCE_RAW_MISSING",
                             "сырое содержимое пусто: зеркалу нечего хранить",
                             origin,
                             command="ttask new <заголовок> --from-text <текст>")
        if system not in schema.SRC_SYSTEMS:
            raise SkillError("KEY_UNKNOWN",
                             "системы источника «%s» нет" % system, origin,
                             hint="система источника — %s"
                                  % ", ".join(schema.SRC_SYSTEMS),
                             command="ttask new <заголовок> --from-text <текст> "
                                     "--source-system %s"
                                     % "|".join(schema.SRC_SYSTEMS))
        record = queue.create(args.title, "mirror", status="mirror")
        source_id = getattr(args, "source_id", None) or origin
        record.data["source"] = {
            "system": system,
            "id": source_id,
            "url": None,
            "imported_at": now_stamp(),
            "by": self.require_by(args, "создание зеркала"),
            "raw": text,
            "revision": 1,
        }
        queue.save(record)
        child = ("ttask new «Формализация стадии: %s» --type intake --parent %s "
                 "--by <имя>" % (record.title, record.id))
        lines = [record_line(queue.index.find(record.id)),
                 "зеркало создано: сырое содержимое %d зн. / %d Б лежит в записи, "
                 "файла снимка нет" % (len(text), len(text.encode("utf-8"))),
                 "правит зеркало только импорт: editor import_only",
                 "черновик дочерней записи формализации создаёт человек: %s" % child]
        payload = {"id": record.id, "type": "mirror", "path": record.path,
                   "source": record.data["source"], "child_draft_command": child}
        return self.print_lines(lines, payload, counts=queue.counts(),
                                next_action=child)

    # --- чтение ---
    def cmd_show(self, args):
        queue = self.resolve_queue(args)
        record, address = self._address(queue, args.address)
        mode = getattr(args, "mode", None)
        if not mode:
            if str(record.id).startswith("D-"):
                mode = "report"
            elif address:
                mode = "comment" if address.startswith("C-") else "element"
            else:
                mode = _default_mode(record, queue.settings)
        settings = dict(queue.settings)
        if getattr(args, "last", None):
            settings["handoff_last"] = int(args.last)
        lines = render_show(record, mode, address, settings)
        return self.print_lines(lines, {"id": record.id, "mode": mode,
                                        "sizes": record.sizes(),
                                        "text": "\n".join(lines)})

    def cmd_pack(self, args):
        """Пакет субагенту одним вызовом: запись, инструкция типа, лента, указатели."""
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        types = TypeIndex(self.paths()["types"])
        if not types.has(record.kind):
            raise SkillError("TYPE_UNKNOWN",
                             "тип «%s» записи %s не объявлен"
                             % (record.kind, record.id),
                             self.paths()["types"], command="tcheck types list")
        mode = getattr(args, "mode", None) or "handoff"
        if mode not in PACK_MODES:
            raise SkillError("READ_MODE_UNKNOWN",
                             "режим ленты «%s» для пакета неизвестен" % mode,
                             "ttask pack %s" % record.id,
                             hint="режим ленты в пакете — %s" % ", ".join(PACK_MODES),
                             command="ttask pack %s --mode %s"
                                     % (record.id, "|".join(PACK_MODES)))
        settings = dict(queue.settings)
        if getattr(args, "last", None):
            settings["handoff_last"] = int(args.last)

        instruction_path = os.path.join(self.paths()["types"], record.kind,
                                        "instruction.md")
        if not os.path.isfile(instruction_path):
            raise SkillError("PACK_INCOMPLETE",
                             "инструкции типа «%s» нет: пакет собрать нельзя"
                             % record.kind, instruction_path,
                             command="tcheck types show %s" % record.kind)
        with open(instruction_path, "r", encoding="utf-8") as handle:
            instruction = handle.read().strip()
        shared_path = os.path.join(self.paths()["types"], "_shared",
                                   "subagent-brief.md")
        if not os.path.isfile(shared_path):
            raise SkillError("PACK_INCOMPLETE",
                             "общего брифа субагенту нет: %s" % shared_path,
                             shared_path,
                             command="tcheck types show %s" % record.kind)
        with open(shared_path, "r", encoding="utf-8") as handle:
            shared_brief = handle.read().strip()

        brief = Brief(self.paths()["types"], settings)
        agents = brief.agents(record.kind)
        agent = brief.agent(record.kind, args.agent) if getattr(args, "agent", None) \
            else (agents[0] if agents else None)

        lines = ["# Пакет субагенту — запись %s" % record.id,
                 "", "## Общий бриф", "", shared_brief,
                 "", "## Инструкция типа %s" % record.kind, "", instruction,
                 "", "## Запись", "", record.body_text(),
                 "", "## Лента: режим %s" % mode, ""]
        lines += render_show(record, mode if mode in SHOW_MODES else "handoff",
                             None, settings)
        lines += ["", "## Указатели (%d)" % len(record.refs)]
        lines += [_ref_line(r) for r in record.refs] or ["указателей нет"]
        lines += ["", "## Артефакты (%d)" % len(record.artifacts)]
        lines += [_artifact_line(a, record.folder) for a in record.artifacts] \
            or ["артефактов нет"]
        lines += ["", "## Возвратный контракт"]
        if agent is not None:
            for issue in agent.validate():
                if issue.code == "PACK_INCOMPLETE":
                    raise SkillError("PACK_INCOMPLETE", issue.message, issue.where,
                                     command="tcheck types show %s" % record.kind)
            lines += ["Субагент: %s (роль %s)." % (agent.agent_id, agent.role),
                      "Поля ответа: %s."
                      % ", ".join(agent.contract.get("fields") or []),
                      "Состав и порядок: %s" % agent.contract.get("shape"),
                      "Большой вывод писать в: %s" % agent.contract.get("persist"),
                      "Вернуть наружу: %s" % agent.contract.get("pointer"),
                      "Границы: %s" % ("; ".join(agent.boundaries)
                                       or "не объявлены")]
        else:
            lines.append("Субагент типа не объявлен: контракт берётся из брифа "
                         "types/_shared/subagent-brief.md.")
        payload = {"id": record.id, "type": record.kind, "mode": mode,
                   "agent": agent.agent_id if agent else None,
                   "brief": shared_path, "instruction": instruction_path,
                   "refs": record.refs,
                   "artifacts": record.artifacts, "sizes": record.sizes(),
                   "text": "\n".join(lines)}
        return self.print_lines(lines, payload)

    def cmd_tree(self, args):
        queue = self.resolve_queue(args)
        root, by_parent = tree_of(queue, args.address)
        lines = render_tree(root, by_parent)
        return self.print_lines(lines, {"id": root.id,
                                        "descendants": _flatten(by_parent, root.id)},
                                counts=queue.counts(),
                                next_action="ttask show %s" % root.id)

    def cmd_digest(self, args):
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        part = getattr(args, "part", None)
        if part:
            text = digest_part(record, part, queue.settings)
            lines = [text.rstrip(),
                     sizes_line(record.sizes(), "часть выгрузки «%s»" % part)]
            return self.print_lines(lines, {"id": record.id, "part": part,
                                            "chars": len(text),
                                            "bytes": len(text.encode("utf-8"))})
        path, text = digest_write(record, queue.settings)
        queue.save(record)
        threshold = int(queue.settings.get("digest_chars", 40000))
        chars, size = len(text), len(text.encode("utf-8"))
        lines = ["выгрузка создана: %s" % path,
                 "размер %d зн. / %d Б; порог настройки проекта %d зн."
                 % (chars, size, threshold),
                 "состав частей: тело записи, оглавление ленты, лента дословно",
                 "файл помечен производным в артефактах: источник правды task.json"]
        if chars > threshold:
            lines.append("файл целиком может не дочитаться: брать частями")
        for name in PARTS:
            lines.append("часть «%s»: ttask digest %s --part %s"
                         % (name, record.id, name))
        lines.append("часть ленты по диапазону: ttask digest %s --part comments:1-5"
                     % record.id)
        lines.extend(_navigation(record))
        return self.print_lines(lines, {"id": record.id, "path": path,
                                        "chars": chars, "bytes": size,
                                        "threshold": threshold,
                                        "parts": list(PARTS)},
                                counts=queue.counts(),
                                next_action="ttask digest %s --part body"
                                            % record.id)

    # --- правка полей ---
    def cmd_set(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        if getattr(args, "id", None):
            raise SkillError("ID_IMMUTABLE",
                             "идентификатор записи неизменен после создания",
                             "ttask set --id", hint="продолжение — дочерняя запись",
                             command="ttask new <заголовок> --type <тип> "
                                     "--parent <id> --by <имя>")
        if getattr(args, "type", None):
            raise SkillError("TYPE_IMMUTABLE",
                             "тип записи неизменен после создания",
                             "ttask set --type", hint="продолжение — дочерняя запись",
                             command="ttask new <заголовок> --type <тип> "
                                     "--parent <id> --by <имя>")
        ids = self.ids_of(args)
        if not ids:
            raise SkillError("ASK_USER", "записи не названы", "ttask set",
                             hint="назвать идентификаторы или передать их из stdin",
                             command="ttask set T-001 T-002 --phase 3 --by <имя>")
        who = self.require_by(args, "правка полей")
        changes = _changes(args)
        extras = _extras(args)
        depends = getattr(args, "depends_on", None)
        if not changes and not extras and not depends:
            raise SkillError("ASK_USER", "ни одно поле не названо", "ttask set",
                             hint="назвать поле флагом или поле типа через --extra",
                             command="ttask set %s --phase 3 --by %s" % (ids[0], who))
        lines = []
        touched = []
        for task_id in ids:
            record = queue.resolve(task_id)
            self._guard_editor(record, types, "ttask set")
            for key, value in changes.items():
                record.data[key] = value
            if depends:
                record.data["depends_on"] = [x.strip() for x in depends.split(",")
                                             if x.strip()]
            for name, value in extras.items():
                record.extra[name] = value
            record.add_comment("правка полей: %s"
                               % _describe(changes, extras, depends), who,
                               kind="human")
            queue.save(record)
            touched.append(record)
            lines.append(record_line(queue.index.find(record.id)))
        issues = _validate_all(types, touched)
        payload = {"ids": [r.id for r in touched], "changes": changes,
                   "extra": extras, "findings": [i.as_dict() for i in issues]}
        code = self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="tcheck validate %s"
                                            % " ".join(r.id for r in touched))
        return _with_findings(code, issues, self)

    def cmd_status(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        status = getattr(args, "status", None)
        if not status:
            raise SkillError("ASK_USER", "новый статус не назван", "ttask status",
                             hint="статус — %s" % ", ".join(schema.STATUSES),
                             command="ttask status <id> --status ready --by <имя>")
        if status not in schema.STATUSES:
            raise SkillError("STATUS_UNKNOWN",
                             "статуса «%s» нет среди объявленных" % status,
                             "ttask status",
                             hint="статус — %s" % ", ".join(schema.STATUSES),
                             command="ttask status <id> --status %s --by <имя>"
                                     % "|".join(schema.STATUSES))
        ids = self.ids_of(args)
        if getattr(args, "all", False) or not ids:
            rows = queue.rows()
            kind = getattr(args, "type", None)
            if kind:
                rows = [r for r in rows if r.get("type") == kind]
            ids = [r["id"] for r in rows
                   if r.get("status") not in ("closed", "cancelled", status)]
        if not ids:
            raise SkillError("RECORD_NOT_FOUND", "записей для перевода нет",
                             "ttask status", command="tqueue list")
        who = self.require_by(args, "перевод статуса")
        reason = getattr(args, "reason", None)
        lines = []
        touched = []
        findings = []
        for task_id in ids:
            record = queue.resolve(task_id)
            self._guard_editor(record, types, "ttask status")
            previous = record.status
            if status == "closed":
                typedef = types.get(record.kind) if types.has(record.kind) else None
                report = _load_report(record)
                gate_issues = close_issues(record, typedef, report)
                if any(i.is_error for i in gate_issues):
                    findings.extend(gate_issues)
                    lines.append("%s статус не переведён: гейты типа %s не пройдены"
                                 % (record.id, record.kind))
                    continue
            record.data["status"] = status
            if status == "in_progress" and not record.data.get("started_at"):
                record.data["started_at"] = now_stamp()
            if status == "blocked" and reason:
                record.data["blocked_reason"] = reason
            record.add_comment("статус %s → %s%s"
                               % (previous, status,
                                  ": %s" % reason if reason else ""), who,
                               kind="human")
            queue.save(record)
            touched.append(record)
            lines.append(record_line(queue.index.find(record.id)))
        payload = {"ids": [r.id for r in touched], "status": status,
                   "findings": [i.as_dict() for i in findings]}
        code = self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="tqueue board")
        return _with_findings(code, findings, self)

    def cmd_claim(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask claim")
        who = getattr(args, "owner", None) or self.require_by(args, "аренда записи")
        owner = record.data.get("owner")
        if owner and owner != who:
            raise SkillError("ASK_USER",
                             "запись %s уже взята: владелец %s" % (record.id, owner),
                             record.id,
                             hint="освободить аренду или договориться с владельцем",
                             command="ttask unclaim %s --by %s" % (record.id, owner))
        record.data["owner"] = who
        if record.status in ("draft", "ready"):
            record.data["status"] = "in_progress"
            record.data["started_at"] = now_stamp()
        record.add_comment("запись взята в работу: %s" % who, who, kind="human")
        queue.save(record)
        return self.print_lines([record_line(queue.index.find(record.id))],
                                {"id": record.id, "owner": who},
                                counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    def cmd_unclaim(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask unclaim")
        who = self.require_by(args, "освобождение аренды")
        owner = record.data.get("owner")
        record.data["owner"] = None
        record.add_comment("аренда освобождена: прежний владелец %s"
                           % (owner or "-"), who, kind="human")
        queue.save(record)
        return self.print_lines([record_line(queue.index.find(record.id))],
                                {"id": record.id, "owner": None},
                                counts=queue.counts(),
                                next_action="tqueue next")

    # --- отчёт и закрытие ---
    def cmd_report_skeleton(self, args):
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        path = os.path.join(record.folder, "report.json")
        skeleton = _report_skeleton(record)
        _write_json(path, skeleton)
        record.add_artifact("report", "report.json", "каркас отчёта закрытия",
                            derived=True)
        queue.save(record)
        lines = ["каркас отчёта создан: %s" % path,
                 "ключи отчёта: %s" % ", ".join(schema.REPORT_KEYS),
                 "заполнить и закрыть: ttask close %s --report report.json "
                 "--by <имя>" % record.id]
        return self.print_lines(lines, {"id": record.id, "path": path,
                                        "keys": list(schema.REPORT_KEYS)},
                                counts=queue.counts(),
                                next_action="ttask close %s --report report.json"
                                            % record.id)

    def cmd_close(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask close")
        who = self.require_by(args, "закрытие записи")
        typedef = types.get(record.kind) if types.has(record.kind) else None
        report = _load_report(record, getattr(args, "report", None))
        if report is None:
            report = _report_skeleton(record)
        if getattr(args, "verdict", None):
            verdict = args.verdict
            if verdict not in ("met", "not_met", "blocked"):
                raise SkillError("KEY_UNKNOWN",
                                 "вердикт «%s» не из met, not_met, blocked" % verdict,
                                 "ttask close", command="ttask close %s --verdict "
                                 "met|not_met|blocked --by <имя>" % record.id)
            report["verdict"] = verdict
            for item in report.get("acceptance_status") or []:
                if isinstance(item, dict) and not item.get("status"):
                    item["status"] = verdict
        report["completed_by"] = who
        report["completed_at"] = now_stamp()
        issues = close_issues(record, typedef, report)
        report_path = os.path.join(record.folder, "report.json")
        _write_json(report_path, report)
        if any(i.is_error for i in issues):
            self.err.write("\n".join(i.as_line() for i in issues) + "\n")
            self.print_lines(["запись %s не закрыта: находок %d"
                              % (record.id, len(issues)),
                              "отчёт лежит в папке записи: %s" % report_path],
                             {"id": record.id, "closed": False,
                              "findings": [i.as_dict() for i in issues]})
            return EXIT_FINDINGS
        record.data["report"] = report
        record.data["status"] = "closed"
        record.add_artifact("report", "report.json", "отчёт закрытия")
        record.add_comment("запись закрыта: %s" % who, who, kind="handoff")
        queue.save(record)
        lines = [record_line(queue.index.find(record.id)),
                 "отчёт закрытия: %s" % report_path]
        return self.print_lines(lines, {"id": record.id, "closed": True,
                                        "report": report}, counts=queue.counts(),
                                next_action="tqueue board")

    def cmd_reopen(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask reopen")
        who = self.require_by(args, "возврат в работу")
        reason = getattr(args, "reason", None)
        if not reason:
            raise SkillError("ASK_USER", "причина возврата не названа",
                             "ttask reopen %s" % record.id,
                             hint="причина пишется в ленту",
                             command="ttask reopen %s --reason <текст> --by <имя>"
                                     % record.id)
        record.data["status"] = "in_progress"
        record.add_comment("запись возвращена в работу: %s" % reason, who,
                           kind="human")
        queue.save(record)
        return self.print_lines([record_line(queue.index.find(record.id))],
                                {"id": record.id, "status": "in_progress"},
                                counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    # --- лента реплик ---
    def cmd_comment(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "ttask comment",
                             hint="вложенные команды: add, list, brief, apply, reject",
                             command="ttask comment list <id>")
        return getattr(self, "_comment_%s" % action)(args)

    def _comment_add(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        body = getattr(args, "body", None)
        if not body or not str(body).strip():
            raise SkillError("EMPTY", "текст реплики пуст", "ttask comment add",
                             hint="реплика — содержательный текст",
                             command="ttask comment add %s --body <текст> --by <имя>"
                                     % record.id)
        who = self.require_by(args, "реплика в ленте")
        kind = getattr(args, "kind", None) or "human"
        self._guard_mirror_comment(record, types)
        item = record.add_comment(body, who, kind=kind)
        if getattr(args, "question", False):
            item["question"] = True
        queue.save(record)
        sizes = record.sizes()
        lines = ["реплика %s добавлена: род %s, автор %s"
                 % (item["id"], kind, who),
                 "лента: %d %s, %d зн. / %d Б"
                 % (sizes["comments_count"], _plural(sizes["comments_count"]),
                    sizes["comments_chars"], sizes["comments_bytes"])]
        return self.print_lines(lines, {"id": record.id, "comment": item},
                                counts=queue.counts(),
                                next_action="ttask show %s --mode comments"
                                            % record.id)

    def _comment_list(self, args):
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        kind = getattr(args, "kind", None)
        items = [c for c in record.comments if not kind or c.get("kind") == kind]
        lines = ["%s %s %s %s" % (c.get("id"), c.get("at"), c.get("by"),
                                  c.get("kind")) for c in items]
        lines.append("реплик %d из %d" % (len(items), len(record.comments)))
        return self.print_lines(lines, {"id": record.id, "comments": items},
                                counts=queue.counts(),
                                next_action="ttask show %s --mode comments"
                                            % record.id)

    def _comment_brief(self, args):
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        last = int(getattr(args, "last", None)
                   or queue.settings.get("handoff_last", 3))
        picked, rest = record.tail(last)
        lines = ["хвост ленты: последние %d %s и все рода handoff"
                 % (last, _plural(last))]
        for item in picked:
            lines.append("%s %s %s %s\n%s" % (item.get("id"), item.get("at"),
                                              item.get("by"), item.get("kind"),
                                              item.get("text")))
        if rest > 0:
            lines.append("не отдано %d %s: ttask show %s --mode comments"
                         % (rest, _plural(rest), record.id))
        else:
            lines.append("отдана вся лента: %d %s"
                         % (len(picked), _plural(len(picked))))
        return self.print_lines(lines, {"id": record.id, "comments": picked,
                                        "rest": rest}, counts=queue.counts(),
                                next_action="ttask pack %s" % record.id)

    def _comment_apply(self, args):
        return self._proposal(args, accepted=True)

    def _comment_reject(self, args):
        return self._proposal(args, accepted=False)

    def _proposal(self, args, accepted):
        queue = self.resolve_queue(args)
        record = queue.resolve(args.address)
        who = self.require_by(args, "решение по предложению")
        comment_id = getattr(args, "comment", None)
        item = record.comment(comment_id) if comment_id else None
        if item is None:
            raise SkillError("RECORD_NOT_FOUND",
                             "реплики «%s» в ленте записи %s нет"
                             % (comment_id, record.id), record.id,
                             command="ttask comment list %s" % record.id)
        if item.get("kind") != "proposal":
            raise SkillError("ASK_USER",
                             "реплика %s рода «%s»: решение принимается по "
                             "предложению" % (comment_id, item.get("kind")),
                             record.id, hint="род реплики — proposal",
                             command="ttask comment list %s --kind proposal"
                                     % record.id)
        note = getattr(args, "note", None)
        item["resolution"] = "accepted" if accepted else "rejected"
        item["resolved_by"] = who
        item["resolved_at"] = now_stamp()
        record.add_comment("предложение %s %s%s"
                           % (comment_id, "принято" if accepted else "отклонено",
                              ": %s" % note if note else ""), who, kind="human")
        queue.save(record)
        lines = ["предложение %s %s: %s"
                 % (comment_id, "принято" if accepted else "отклонено",
                    note or "без пояснения")]
        return self.print_lines(lines, {"id": record.id, "comment": item},
                                counts=queue.counts(),
                                next_action="ttask show %s --mode comments"
                                            % record.id)

    # --- указатели и артефакты ---
    def cmd_ref(self, args):
        return self._nested(args, "ref")

    def cmd_artifact(self, args):
        return self._nested(args, "artifact")

    def _nested(self, args, table):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "ttask %s" % table,
                             hint="вложенные команды: add, remove, rename",
                             command="ttask %s add <id> --kind <род> --path <путь> "
                                     "--note <пояснение> --by <имя>" % table)
        return getattr(self, "_%s_%s" % (table, action))(args)

    def _ref_add(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask ref add")
        note = self._require_note(args, "указатель")
        kind = getattr(args, "kind", None) or "file"
        if not getattr(args, "path", None):
            raise SkillError("ASK_USER", "путь указателя не назван", "ttask ref add",
                             hint="назвать файл, символ, URL или id записи",
                             command="ttask ref add %s --kind %s --path <путь> --note <пояснение> --by <имя>"
                                     % (record.id, kind))
        if kind not in schema.REF_KINDS:
            raise SkillError("KEY_UNKNOWN", "рода указателя «%s» нет" % kind,
                             "ttask ref add",
                             hint="род указателя — %s" % ", ".join(schema.REF_KINDS),
                             command="ttask ref add %s --kind %s --path <путь> "
                                     "--note <пояснение>"
                                     % (record.id, "|".join(schema.REF_KINDS)))
        ref = record.add_ref(kind, args.path, note,
                             symbol=getattr(args, "symbol", None),
                             lines=getattr(args, "lines", None),
                             found_by=getattr(args, "found_by", None),
                             by=getattr(args, "by", None))
        queue.save(record)
        return self.print_lines([_ref_line(ref), "указателей %d" % len(record.refs)],
                                {"id": record.id, "ref": ref},
                                counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    def _ref_remove(self, args):
        return self._pointer_remove(args, "refs", "указатель")

    def _ref_rename(self, args):
        return self._pointer_rename(args, "refs", "указатель")

    def _artifact_add(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask artifact add")
        kind = getattr(args, "kind", None) or "other"
        if kind not in schema.ARTEFACT_KINDS:
            raise SkillError("KEY_UNKNOWN", "рода артефакта «%s» нет" % kind,
                             "ttask artifact add",
                             hint="род артефакта — %s"
                                  % ", ".join(schema.ARTEFACT_KINDS),
                             command="ttask artifact add %s --kind %s --path <файл>"
                                     % (record.id, "|".join(schema.ARTEFACT_KINDS)))
        path = getattr(args, "path", None)
        if not path:
            raise SkillError("ASK_USER", "путь артефакта не назван",
                             "ttask artifact add", command="ttask artifact add %s --kind %s --path <файл> --note <пояснение> --by <имя>"
                             % (record.id, kind))
        full = path if os.path.isabs(path) else os.path.join(record.folder, path)
        if not os.path.isfile(full):
            raise SkillError("ARTIFACT_MISSING",
                             "файла артефакта «%s» нет в папке записи" % path, full,
                             hint="сначала положить файл в папку записи",
                             command="ttask artifact add %s --kind %s --path %s "
                                     "--by <имя>" % (record.id, kind, path))
        art = record.add_artifact(kind, path, getattr(args, "note", None) or "",
                                  derived=bool(getattr(args, "derived", False)),
                                  by=getattr(args, "by", None))
        queue.save(record)
        return self.print_lines([_artifact_line(art, record.folder),
                                 "артефактов %d" % len(record.artifacts)],
                                {"id": record.id, "artifact": art},
                                counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    def _artifact_remove(self, args):
        return self._pointer_remove(args, "artifacts", "артефакт")

    def _artifact_rename(self, args):
        return self._pointer_rename(args, "artifacts", "артефакт")

    def _pointer_remove(self, args, table, what):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask %s remove" % table.rstrip("s"))
        note = self._require_note(args, what)
        who = self.require_by(args, "удаление: %s" % what)
        path = getattr(args, "path", None)
        items = record.data.get(table) or []
        kept = [i for i in items
                if not (isinstance(i, dict) and i.get("path") == path)]
        if len(kept) == len(items):
            raise SkillError("RECORD_NOT_FOUND",
                             "%s с путём «%s» в записи %s не найден"
                             % (what, path, record.id), record.id,
                             command="ttask show %s" % record.id)
        record.data[table] = kept
        record.add_comment("%s убран: %s (%s)"
                           % (what.capitalize(), path, note), who, kind="human")
        queue.save(record)
        return self.print_lines(["%s убран: %s; осталось %d" % (what, path, len(kept))],
                                {"id": record.id, "removed": path,
                                 "left": len(kept)}, counts=queue.counts(),
                                next_action="ttask show %s" % record.id)

    def _pointer_rename(self, args, table, what):
        """Переименование: пояснение обязательно, журнал — реплика в ленте."""
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask %s rename" % table.rstrip("s"))
        note = self._require_note(args, "переименование: %s" % what)
        old, new = getattr(args, "old", None), getattr(args, "new", None)
        if not old or not new:
            raise SkillError("ASK_USER",
                             "прежнее и новое значение пути не названы",
                             "ttask %s rename %s" % (table.rstrip("s"), record.id),
                             hint="назвать прежнее и новое значение",
                             command="ttask %s rename %s --old <путь> --new <путь> "
                                     "--note <пояснение> --by <имя>"
                                     % (table.rstrip("s"), record.id))
        who = self.require_by(args, "переименование: %s" % what)
        changed = record.rename_pointer(table, old, new, note, who)
        if not changed:
            raise SkillError("RECORD_NOT_FOUND",
                             "%s с путём «%s» в записи %s не найден"
                             % (what, old, record.id), record.id,
                             command="ttask show %s" % record.id)
        queue.save(record)
        lines = ["%s переименован: прежний %s, новый %s" % (what, old, new),
                 "реплика в ленте: %s" % record.comments[-1].get("id"),
                 "отдельного файла журнала операций нет"]
        return self.print_lines(lines, {"id": record.id, "old": old, "new": new},
                                counts=queue.counts(),
                                next_action="ttask show %s --mode comments"
                                            % record.id)

    def cmd_evidence(self, args):
        """Свидетельство прогона: гейт типа проверяет наличие при закрытии."""
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        record = queue.resolve(args.address)
        self._guard_editor(record, types, "ttask evidence")
        kind = getattr(args, "kind", None) or "log"
        if kind not in EVIDENCE_KINDS:
            raise SkillError("KEY_UNKNOWN",
                             "рода свидетельства «%s» нет" % kind, "ttask evidence",
                             hint="род свидетельства — %s"
                                  % ", ".join(EVIDENCE_KINDS),
                             command="ttask evidence %s --kind log --path <файл>"
                                     % record.id)
        path = getattr(args, "path", None)
        if not path:
            raise SkillError("ASK_USER", "путь свидетельства не назван",
                             "ttask evidence", command="ttask evidence %s --kind %s --path <файл> --by <имя>"
                             % (record.id, kind))
        full = path if os.path.isabs(path) else os.path.join(record.folder, path)
        if not os.path.isfile(full):
            raise SkillError("ARTIFACT_MISSING",
                             "файла свидетельства «%s» нет" % path, full,
                             hint="положить файл прогона в папку записи",
                             command="ttask evidence %s --kind %s --path %s "
                                     "--by <имя>" % (record.id, kind, path))
        note = getattr(args, "note", None) or "свидетельство прогона"
        art = record.add_artifact(kind, path, note, by=getattr(args, "by", None))
        who = getattr(args, "by", None)
        if who:
            record.add_comment("свидетельство прогона: %s (%s)" % (path, note),
                               who, kind="human")
        queue.save(record)
        lines = [_artifact_line(art, record.folder),
                 "гейт теста проверяет свидетельство при закрытии записи"]
        return self.print_lines(lines, {"id": record.id, "artifact": art},
                                counts=queue.counts(),
                                next_action="ttask close %s --by <имя>" % record.id)

    def cmd_link(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        parent = queue.resolve(args.parent)
        child = queue.resolve(args.child)
        self._guard_editor(parent, types, "ttask link")
        note = self._require_note(args, "связь записей")
        ref = link_records(parent, child.id, note, by=getattr(args, "by", None))
        queue.save(parent)
        lines = ["связь проставлена: %s → %s" % (parent.id, child.id),
                 _ref_line(ref),
                 "содержимое ребёнка осталось в его записи: ничего не скопировано"]
        return self.print_lines(lines, {"parent": parent.id, "child": child.id,
                                        "ref": ref}, counts=queue.counts(),
                                next_action="ttask tree %s" % parent.id)

    # --- массовые операции ---
    def cmd_batch(self, args):
        """Пакет операций одной транзакцией: либо все, либо ни одной."""
        queue = self.resolve_queue(args)
        path = args.ops
        if not os.path.isfile(path):
            raise SkillError("RECORD_NOT_FOUND",
                             "файла операций «%s» нет" % path, path,
                             command="ttask batch ops.json --dry-run")
        with open(path, "r", encoding="utf-8") as handle:
            try:
                ops = json.load(handle)
            except ValueError as exc:
                raise SkillError("JSON_MALFORMED",
                                 "файл операций не разбирается как JSON: %s" % exc,
                                 path, command="ttask batch ops.json")
        if not isinstance(ops, list):
            raise SkillError("JSON_MALFORMED",
                             "файл операций — массив объектов {op, id, значения}",
                             path, command="ttask batch ops.json --dry-run")
        if bool(getattr(args, "dry_run", False)):
            lines = ["план: операций %d, ничего не пишется" % len(ops)]
            lines += ["%d. %s" % (pos, _op_line(op))
                      for pos, op in enumerate(ops, start=1)]
            return self.print_lines(lines, {"dry_run": True, "count": len(ops),
                                            "ops": ops}, counts=queue.counts(),
                                    next_action="ttask batch %s --by <имя>" % path)
        snapshot = tempfile.mkdtemp(prefix="todone-batch-")
        backup = os.path.join(snapshot, "todone")
        if os.path.isdir(queue.todone_dir):
            shutil.copytree(queue.todone_dir, backup)
        results = []
        failed = None
        for pos, op in enumerate(ops, start=1):
            try:
                self._run_op(op, args)
                results.append({"pos": pos, "op": op,
                                "line": "%d. %s → выполнено" % (pos, _op_line(op))})
            except SkillError as exc:
                failed = exc
                results.append({"pos": pos, "op": op,
                                "line": "%d. %s → отказ %s"
                                        % (pos, _op_line(op), exc.as_line())})
                break
        if failed is not None:
            shutil.rmtree(queue.todone_dir, ignore_errors=True)
            if os.path.isdir(backup):
                shutil.copytree(backup, queue.todone_dir)
            queue._store = None
            queue._index = None
        shutil.rmtree(snapshot, ignore_errors=True)
        lines = [r["line"] for r in results]
        lines.append("транзакция откачена: операций выполнено 0 из %d" % len(ops)
                     if failed is not None
                     else "транзакция выполнена: операций %d" % len(ops))
        payload = {"ops": len(ops), "done": 0 if failed else len(ops),
                   "rolled_back": failed is not None,
                   "results": [{"pos": r["pos"], "op": r["op"]} for r in results]}
        code = self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="tqueue board")
        if failed is not None:
            self.err.write(failed.as_line() + "\n")
            return EXIT_FINDINGS
        return code

    def _run_op(self, op, args):
        """Одна операция пакета: тот же обработчик, что и у команды."""
        if not isinstance(op, dict) or "op" not in op:
            raise SkillError("JSON_MALFORMED", "операция без ключа «op»",
                             "ttask batch",
                             command="ttask batch ops.json --dry-run")
        name = str(op["op"]).replace("-", "_")
        handler = getattr(self, "cmd_%s" % name, None)
        if handler is None:
            raise SkillError("NOT_IMPLEMENTED",
                             "операции «%s» точка входа %s не знает"
                             % (op["op"], self.entry), "ttask batch",
                             command="ttask batch ops.json --dry-run")
        return handler(_op_args(op, args))

    # --- documentation intent ---
    def cmd_document(self, args):
        """Handle explicit documentation intent through the docs domain.

        The command never treats ordinary task text as a policy change.  With
        no content it writes a bounded DOC-CAPTURE-1 request; with content it
        writes one validated DOC-1 revision through DocumentationWorkspace.
        """
        who = self.require_by(args, "документация")
        workspace = DocumentationWorkspace(self.root,
                                           docs_path=getattr(args, "docs_path", None))
        if workspace.manifest is None:
            raise SkillError("DOC_WORKSPACE_MISSING",
                             "для explicit documentation intent нужен docs manifest",
                             workspace.manifest_path,
                             command="tcheck docs init --root %s" % self.root)
        policy = workspace.policy()
        if policy.get("automation") == "disabled":
            raise SkillError("DOC_POLICY_DISABLED",
                             "explicit documentation запрещена policy=disabled",
                             workspace.manifest_path)
        ids = self.ids_of(args)
        task_refs = []
        changed_files = list(getattr(args, "changed_file", None) or [])
        queue = self.resolve_queue(args, required=False)
        records = []
        if queue is not None:
            for task_id in ids:
                record = queue.resolve(task_id)
                records.append(record)
                task_refs.append("%s:%s:%s" % (queue.alias, record.kind, record.id))
                for ref in record.refs:
                    if ref.get("kind") == "file" and ref.get("path"):
                        changed_files.append(ref["path"])
        capture_data = None
        from_chat = getattr(args, "from_chat", None)
        if from_chat:
            try:
                with open(from_chat, "r", encoding="utf-8") as handle:
                    capture_data = json.load(handle)
            except (OSError, ValueError) as exc:
                raise SkillError("DOC_CAPTURE_INVALID", "capture не читается: %s" % exc,
                                 from_chat)
            from .documentation import validate_capture
            issues = validate_capture(capture_data, from_chat)
            if any(item.is_error for item in issues):
                first = issues[0]
                raise SkillError(first.code, first.message, first.where)
            task_refs = list(capture_data.get("task_refs") or task_refs)
            changed_files = list(capture_data.get("changed_files") or changed_files)
        doc_keys = list(getattr(args, "doc_key", None) or [])
        if not doc_keys:
            for record in records:
                impact = record.extra.get("documentation_impact")
                if isinstance(impact, dict):
                    doc_keys.extend(impact.get("doc_keys") or [])
        if not doc_keys and records:
            doc_keys = ["change/%s" % records[0].id]
        # One capture may name many tasks, but a canonical module is written
        # once per doc_key, never once per participating task.
        doc_keys = list(dict.fromkeys(doc_keys))
        release = getattr(args, "release", None)
        release_context = {"release": release} if release else {}
        if capture_data is not None:
            result = capture_data
        else:
            result = workspace.capture(task_refs=task_refs, doc_keys=doc_keys,
                                       release_context=release_context,
                                       user_intent="задокументируй",
                                       changed_files=changed_files,
                                       by=who)
        content = getattr(args, "content", None)
        written = []
        if content is not None:
            if not doc_keys:
                raise SkillError("DOC_CAPTURE_EMPTY",
                                 "для module write нужен --doc-key или active task",
                                 "ttask document")
            machine = _json_file(getattr(args, "machine_file", None))
            claims = _json_file(getattr(args, "claims_file", None))
            if claims is not None:
                issues = validate_claims(claims)
                if any(item.is_error for item in issues):
                    first = issues[0]
                    raise SkillError(first.code, first.message, first.where)
            for key in doc_keys:
                written.append(workspace.write_module(
                    key, getattr(args, "kind", None) or "change", content,
                    machine=machine, claims=claims, source_task_refs=task_refs,
                    source_refs=[{"kind": "file", "path": path, "note": "explicit capture"}
                                 for path in sorted(set(changed_files))],
                    scope=release_context, status="active", by=who, generated=False))
            result["status"] = "applied"
            result["module_revisions"] = [item["module"]["doc_key"] + "@" +
                                           str(item["module"]["revision"])
                                           for item in written]
        lines = ["documentation intent: %s" % ("applied" if written else "captured"),
                 "capture: %s" % result.get("capture_id"),
                 "task refs: %s" % (", ".join(task_refs) or "нет"),
                 "doc keys: %s" % (", ".join(doc_keys) or "нет")]
        if written:
            lines.append("revisions: %s" % ", ".join(result["module_revisions"]))
        payload = {"capture": result, "written": [item["module"] for item in written],
                   "policy": policy}
        return self.print_lines(lines, payload,
                                counts=queue.counts() if queue else {"all": 0},
                                next_action="tcheck docs check --root %s" % self.root)

    # --- поток ---
    def cmd_flow(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "ttask flow",
                             hint="вложенные команды: start, state, next",
                             command="ttask flow state <id>")
        return getattr(self, "_flow_%s" % action)(args)

    def _flow_start(self, args):
        queue = self.resolve_queue(args)
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        flow_id = getattr(args, "flow", None)
        source_id = getattr(args, "from", None)
        if not source_id:
            raise SkillError("ASK_USER", "запись-источник не названа", "ttask flow start",
                             hint="назвать запись-источник", command="ttask flow start --from <id>")
        state = FlowState(queue, flows, TypeIndex(self.paths()["types"]))
        response = _choice_json(getattr(args, "choice_json", None))
        entry_selected = False
        policy_override = None
        if flow_id is None:
            request = flows.entry_choice()
            if response is None and getattr(args, "choice", None) is not None:
                response = {"request_id": request["request_id"], "selection": "single",
                            "value": args.choice, "source": "user",
                            "actor": getattr(args, "by", None), "reason": "CLI entry selection"}
            if response is None:
                raise SkillError("FLOW_CHOICE_REQUIRED",
                                 "на входе нужно выбрать allowlisted flow",
                                 "flow entry selector",
                                 details={"request": request, "source_id": source_id})
            selected = state.select_entry(request, response,
                                          by=getattr(args, "by", None) or "user")
            flow_id = selected["flow"]
            policy_override = selected.get("policy")
            entry_selected = True
        if not entry_selected and response is None and getattr(args, "choice", None) is not None:
            # For a controlled step request id is supplied by --choice-json;
            # a bare choice remains useful only when the request id is explicit.
            response = {"request_id": getattr(args, "request_id", None),
                        "selection": "single", "value": args.choice,
                        "source": "user", "actor": getattr(args, "by", None),
                        "reason": "CLI flow start choice"}
        created, remaining = state.start(flow_id, source_id,
                                         batch=getattr(args, "batch", None),
                                         by=getattr(args, "by", None),
                                         title=getattr(args, "title", None),
                                         choice=response,
                                         disabled=bool(getattr(args, "disabled", False)),
                                         explicit_document=bool(getattr(args, "document_now", False)),
                                         policy_override=policy_override)
        lines = ["поток «%s» запущен: черновиков %d" % (flow_id, len(created))]
        lines += [record_line(queue.index.find(r.id)) for r in created]
        lines.append("в работу черновики переводит человек: ttask status <id> "
                     "--status ready --by <имя>")
        if remaining:
            lines.append("остались шаги: %s — их создаёт следующий вызов той же "
                         "команды" % ", ".join(remaining))
        payload = {"flow": flow_id, "created": [r.id for r in created],
                   "remaining": remaining}
        return self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="ttask flow state %s"
                                            % (created[0].id if created
                                               else source_id))

    def _flow_choice(self, args):
        queue = self.resolve_queue(args)
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        state = FlowState(queue, flows, TypeIndex(paths["types"]))
        flow_id = getattr(args, "flow", None)
        step_id = getattr(args, "step", None)
        source_id = getattr(args, "from", None)
        if getattr(args, "entry", False):
            request = flows.entry_choice()
        else:
            if not flow_id or not step_id:
                raise SkillError("ASK_USER", "flow и step choice не названы",
                                 "ttask flow choice",
                                 command="ttask flow choice --flow <flow> --step <step> "
                                         "--from <id> --value <choice> --by <имя>")
            request = state.choice_request(flow_id, step_id, source_id)
        raw = _choice_json(getattr(args, "choice_json", None))
        if raw is None:
            raw = {"schema": RESPONSE_SCHEMA,
                   "request_id": request["request_id"],
                   "decision_id": request["decision_id"],
                   "selection": request["selection"],
                   "value": getattr(args, "value", None),
                   "values": ([item.strip() for item in str(args.values).split(",")
                               if item.strip()] if getattr(args, "values", None) else None),
                   "text": getattr(args, "text", None),
                   "source": getattr(args, "source", None) or "user",
                   "actor": getattr(args, "by", None),
                   "reason": getattr(args, "reason", None)}
        if getattr(args, "entry", False):
            selected = state.select_entry(request, raw, by=getattr(args, "by", None) or "user")
            return self.print_lines(["выбран allowlisted flow: %s" % selected["flow"],
                                    "preset: %s" % selected["preset"]],
                                   selected, counts=queue.counts(),
                                   next_action="ttask flow start --flow %s --from <id>"
                                               % selected["flow"])
        decision = state.answer_choice(flow_id, source_id, step_id, raw,
                                       by=getattr(args, "by", None),
                                       disabled=bool(getattr(args, "disabled", False)))
        return self.print_lines(["решение сохранено: %s" % decision["decision_id"],
                                "outcome: %s" % decision["outcome"].get("action")],
                               decision, counts=queue.counts(),
                               next_action="ttask flow start --flow %s --from %s"
                                           % (flow_id, source_id))

    def _flow_transition(self, args):
        queue = self.resolve_queue(args)
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        state = FlowState(queue, flows, TypeIndex(paths["types"]))
        source_id = getattr(args, "from", None) or getattr(args, "address", None)
        if not source_id or not getattr(args, "target_flow", None):
            raise SkillError("ASK_USER", "источник и target flow не названы",
                             "ttask flow transition",
                             command="ttask flow transition --from <id> "
                                     "--target-flow <flow> --by <имя>")
        refs = list(getattr(args, "carry_ref", None) or [])
        result = state.transition(source_id, args.target_flow,
                                  target_step=getattr(args, "target_step", None),
                                  choice_ref=getattr(args, "choice_ref", None),
                                  carry_refs=refs,
                                  requested_by=getattr(args, "requested_by", None) or "user",
                                  by=getattr(args, "by", None),
                                  title=getattr(args, "title", None),
                                  scope={"run": True},
                                  release_context={"release": getattr(args, "release", None)}
                                  if getattr(args, "release", None) else None)
        payload = result["transition"]
        return self.print_lines(["flow transition applied: %s" % payload["transition_id"],
                                "old run: %s / %s" % (result["old_run"]["flow"],
                                                      result["old_run"]["status"]),
                                "new run: %s (%s)" % (result["new_run"]["run"],
                                                       result["new_run"]["record"])],
                               result, counts=queue.counts(),
                               next_action="ttask flow state %s" % result["new_run"]["record"])

    def _flow_state(self, args):
        queue = self.resolve_queue(args)
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        state = FlowState(queue, flows, TypeIndex(paths["types"]))
        flow_id = getattr(args, "flow", None)
        address = getattr(args, "address", None)
        row = queue.index.find(address) if address else None
        if not flow_id and row:
            flow_id = row.get("flow")
        if not flow_id:
            raise SkillError("FLOW_STATE_MISMATCH",
                             "поток не назван и запись в потоке не участвует",
                             address or "ttask flow state",
                             command="tcheck flows list")
        flow = flows.get(flow_id)
        source = address if row is not None and not row.get("flow_step") else None
        lines = state.state(flow_id, source)
        run_id = None
        if row is not None:
            run_id = row.get("flow_run") or (address if not row.get("flow_step") else None)
        chain = state.chain(flow, run_id)
        payload = {"flow": flow_id, "run": run_id,
                   "rows": [{"step": item["step"],
                             "id": item["record"].id if item["record"] else None,
                             "status": item["record"].status if item["record"] else None,
                             "item": (item.get("row") or {}).get("flow_item"),
                             "revision": (item.get("row") or {}).get("flow_revision") or 1}
                            for item in chain]}
        first = next((r["id"] for r in payload["rows"] if r["id"]), None)
        return self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="ttask flow next %s" % first
                                if first else "tcheck flows show %s" % flow_id)

    def _flow_next(self, args):
        queue = self.resolve_queue(args)
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        state = FlowState(queue, flows, TypeIndex(paths["types"]))
        current, upcoming, requires, issues = state.next(args.address)
        lines = ["текущий шаг: %s (тип %s)" % (current.id, current.type)]
        if upcoming:
            lines.append("следующие шаги: %s" % ", ".join(
                "%s%s" % (s.id, " (пропускаемый)" if s.optional else "")
                for s in upcoming))
        else:
            lines.append("следующих шагов нет: поток завершается")
        for item in requires:
            lines.append("шаг %s требует от %s: %s; оставлено: %s"
                         % (item["step"], item["from"],
                            ", ".join(item["declared"]) or "-",
                            ", ".join(item["left"]) or "ничего"))
        payload = {"step": current.id, "next": [s.id for s in upcoming],
                   "requires": requires,
                   "findings": [i.as_dict() for i in issues]}
        code = self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="ttask show %s" % args.address)
        return _with_findings(code, issues, self)

    # --- общие вспомогательные ---
    def _address(self, queue, address):
        """Адрес записи или её части: T-014, T-014/C-7, T-014/AC-2, D-001."""
        if not address:
            raise SkillError("ASK_USER", "адрес записи не назван", "ttask show",
                             hint="адрес — идентификатор записи, реплики или "
                                  "элемента",
                             command="ttask show T-001")
        task_id, _, part = str(address).partition("/")
        if task_id.startswith("D-"):
            for owner in queue.records:
                report = _load_report(owner)
                if isinstance(report, dict) and report.get("id") == task_id:
                    data = {"id": task_id,
                            "title": "Отчёт закрытия %s" % owner.id,
                            "kind": "report", "status": "closed",
                            "comments": [], "extra": {}, "refs": [],
                            "artifacts": [], "report": report}
                    return Record(data, path=os.path.join(owner.folder,
                                                          "report.json"),
                                  folder=owner.folder), part or None
            raise SkillError("RECORD_NOT_FOUND",
                             "отчёта «%s» в очереди нет" % task_id, task_id,
                             command="tqueue list --status closed")
        return queue.resolve(task_id), part or None

    def _guard_editor(self, record, types, what):
        """Зеркало правит только импорт: отказ с обходом через дочернюю запись."""
        typedef = types.get(record.kind) if types.has(record.kind) else None
        if typedef is not None and typedef.editor == "import_only":
            raise SkillError("MIRROR_READONLY",
                             "запись %s типа %s правится только импортом: %s"
                             % (record.id, record.kind, what), record.id,
                             hint="продолжение работы — дочерняя запись",
                             command="ttask new <заголовок> --type intake "
                                     "--parent %s --by <имя>" % record.id)

    def _guard_mirror_comment(self, record, types):
        """Комментировать зеркало наружу нельзя: служебное — в дочерней записи."""
        typedef = types.get(record.kind) if types.has(record.kind) else None
        source = record.source
        if typedef is not None and typedef.editor == "import_only" \
                and isinstance(source, dict) \
                and source.get("system") in ("jira", "openspec", "speckit"):
            raise SkillError("COMMENT_SOURCE_LOCKED",
                             "зеркало %s комментировать наружу нельзя" % record.id,
                             record.id,
                             hint="служебная реплика — в дочерней записи",
                             command="ttask new <заголовок> --type intake "
                                     "--parent %s --by <имя>" % record.id)

    def _require_note(self, args, what):
        note = getattr(args, "note", None)
        if not note or not str(note).strip():
            raise SkillError("REF_NOTE_MISSING",
                             "пояснение к операции «%s» не названо" % what,
                             "флаг --note",
                             hint="пояснение — зачем указатель или что изменилось",
                             command="… --note <пояснение> --by <имя>")
        return str(note).strip()


#: Флаги вложенных команд: справка называет каждый используемый флаг.
NESTED_FLAGS = {
    ("comment", "add"): [("address", None, "идентификатор записи"),
                         ("--body", None, "текст реплики дословно"),
                         ("--kind", None,
                          "род реплики: %s" % ", ".join(schema.COMMENT_KINDS)),
                         ("--question", bool, "реплика требует ответа человека")],
    ("comment", "list"): [("address", None, "идентификатор записи"),
                          ("--kind", None, "отбор по роду реплики")],
    ("comment", "brief"): [("address", None, "идентификатор записи"),
                           ("--last", int, "сколько последних реплик отдать")],
    ("comment", "apply"): [("address", None, "идентификатор записи"),
                           ("--comment", None, "идентификатор реплики-предложения"),
                           ("--note", None, "что принято")],
    ("comment", "reject"): [("address", None, "идентификатор записи"),
                            ("--comment", None, "идентификатор реплики-предложения"),
                            ("--note", None, "почему отклонено")],
    ("ref", "add"): [("address", None, "идентификатор записи"),
                     ("--kind", None,
                      "род указателя: %s" % ", ".join(schema.REF_KINDS)),
                     ("--path", None, "путь, символ или идентификатор записи"),
                     ("--note", None, "пояснение: обязательно"),
                     ("--symbol", None, "имя символа"),
                     ("--lines", None, "строки: например 12-40"),
                     ("--found-by", None,
                      "чем найдено: grep, code-graph, человек")],
    ("ref", "remove"): [("address", None, "идентификатор записи"),
                        ("--path", None, "путь указателя, который убирают"),
                        ("--note", None, "пояснение: обязательно")],
    ("ref", "rename"): [("address", None, "идентификатор записи"),
                        ("--old", None, "прежнее значение пути"),
                        ("--new", None, "новое значение пути"),
                        ("--note", None, "пояснение: обязательно")],
    ("artifact", "add"): [("address", None, "идентификатор записи"),
                          ("--kind", None,
                           "род артефакта: %s" % ", ".join(schema.ARTEFACT_KINDS)),
                          ("--path", None, "путь файла в папке записи"),
                          ("--note", None, "пояснение"),
                          ("--derived", bool,
                           "артефакт производный: пересоздаётся командой")],
    ("artifact", "remove"): [("address", None, "идентификатор записи"),
                             ("--path", None, "путь артефакта"),
                             ("--note", None, "пояснение: обязательно")],
    ("artifact", "rename"): [("address", None, "идентификатор записи"),
                             ("--old", None, "прежнее значение пути"),
                             ("--new", None, "новое значение пути"),
                             ("--note", None, "пояснение: обязательно")],
    ("flow", "start"): [("--flow", None, "имя потока из allowlist"),
                        ("--from", None,
                         "запись-источник: зеркало или вход потока"),
                        ("--batch", int,
                         "сколько черновиков создать: не больше объявленного"),
                        ("--title", None, "заголовок черновиков"),
                        ("--choice", None, "явный choice id для controlled step"),
                        ("--choice-json", None, "FLOW-CHOICE-RESPONSE-1 JSON"),
                        ("--request-id", None, "choice request id, если передан --choice"),
                        ("--disabled", bool, "явно disable controlled step"),
                        ("--document-now", bool, "явный documentation intent")],
    ("flow", "state"): [("--flow", None, "имя потока"),
                        ("address", None, "запись потока: печатает цепочку")],
    ("flow", "next"): [("address", None, "идентификатор записи потока")],
    ("flow", "choice"): [("--flow", None, "имя allowlisted потока"),
                         ("--step", None, "controlled step или entry"),
                         ("--from", None, "запись run для решения"),
                         ("--entry", bool, "выбрать flow на входе"),
                         ("--choice-json", None, "FLOW-CHOICE-RESPONSE-1 JSON"),
                         ("--value", None, "single/boolean choice id"),
                         ("--values", None, "multiple choice ids через запятую"),
                         ("--text", None, "text choice, если разрешён flow.json"),
                         ("--source", None, "user или policy; agent recommendation не финал"),
                         ("--reason", None, "пояснение выбора"),
                         ("--disabled", bool, "on_disabled route" )],
    ("flow", "transition"): [("--from", None, "текущая запись старого run"),
                              ("--address", None, "алиас текущей записи"),
                              ("--target-flow", None, "allowlisted target flow"),
                              ("--target-step", None, "target step; обычно entry"),
                              ("--choice-ref", None, "FLOW-CHOICE request/decision ref"),
                              ("--carry-ref", None, "bounded carry ref; флаг повторяется"),
                              ("--requested-by", None, "user, agent или policy"),
                              ("--release", None, "release context"),
                              ("--title", None, "заголовок нового target task")],
}


def _choice_json(path):
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise SkillError("FLOW_CHOICE_INVALID", "choice JSON не читается: %s" % exc, path)
    if not isinstance(data, dict):
        raise SkillError("FLOW_CHOICE_INVALID", "choice response должен быть объектом", path)
    return data


def _json_file(path):
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise SkillError("DOC_CAPTURE_INVALID", "JSON не читается: %s" % exc, path)
    return data


def _picked(args, names):
    picked = {}
    for name in names:
        value = getattr(args, name, None)
        if value is not None:
            picked[name] = value
    return picked


ELEMENT_FLAG_PREFIX = {
    "goals": ("goals", "G"),
    "acceptance": ("acceptance", "AC"),
    "in_scope": ("in_scope", "IN"),
    "out_of_scope": ("out_of_scope", "OUT"),
    "context": ("context", "CT"),
    "files_hint": ("files_hint", "F"),
    "steps": ("steps", "S"),
    "verify": ("verify", "V"),
    "open_questions": ("open_questions", "Q"),
    "notes": ("notes", "N"),
}


def _changes(args):
    changes = _picked(args, SET_FIELDS)
    estimate = getattr(args, "estimate", None)
    if estimate is not None:
        changes["estimate_h"] = _number(estimate, "estimate")
    for field, (target, prefix) in ELEMENT_FLAG_PREFIX.items():
        values = getattr(args, field.replace("_", "-"), None)
        # argparse stores dashes as underscores; the direct attribute is the
        # stable path for both positional and option parser variants.
        if values is None:
            values = getattr(args, field, None)
        if values:
            changes[target] = [{"id": "%s-%d" % (prefix, pos), "text": str(value)}
                               for pos, value in enumerate(values, start=1)]
    return changes


def _number(value, name):
    try:
        return float(value) if "." in str(value) else int(value)
    except ValueError:
        raise SkillError("KEY_UNKNOWN",
                         "значение «%s» поля %s — не число" % (value, name),
                         "ttask set",
                         command="ttask set <id> --%s <число> --by <имя>" % name)


def _extras(args):
    """Дополнительные поля типа из `--extra имя=значение`."""
    extras = {}
    for item in getattr(args, "extra", None) or []:
        name, sep, value = str(item).partition("=")
        if not sep or not name.strip():
            raise SkillError("TYPE_FIELD_UNKNOWN",
                             "дополнительное поле «%s» не в форме имя=значение"
                             % item, "ttask set --extra",
                             hint="имя поля объявляет тип",
                             command="tcheck types fields <тип>")
        extras[name.strip()] = _coerce(value)
    return extras


def _coerce(value):
    text = str(value).strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if text[:1] in ("[", "{"):
        try:
            return json.loads(text)
        except ValueError:
            return text
    try:
        return int(text)
    except ValueError:
        return text


def _describe(changes, extras, depends):
    parts = ["%s=%s" % (k, v) for k, v in sorted(changes.items())]
    parts += ["extra.%s=%s" % (k, v) for k, v in sorted(extras.items())]
    if depends:
        parts.append("depends_on=%s" % depends)
    return ", ".join(parts)


def _validate_all(types, records, strict=True):
    validator = Validator(types)
    issues = []
    for record in records:
        issues.extend(validator.record(record, strict=strict))
    return issues


def _with_findings(code, issues, cli):
    """Находки после правки: печать в stderr и код возврата с находками."""
    errors = [i for i in issues if i.is_error]
    for issue in issues:
        cli.err.write(issue.as_line() + "\n")
    return EXIT_FINDINGS if errors else code


def _load_report(record, name=None):
    path = os.path.join(record.folder or "", name or "report.json")
    if not os.path.isfile(path):
        return record.data.get("report")
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except ValueError as exc:
            raise SkillError("JSON_MALFORMED",
                             "отчёт не разбирается как JSON: %s" % exc, path,
                             command="ttask report-skeleton %s" % record.id)


def _report_skeleton(record):
    """Каркас отчёта закрытия: ключи схемы REPORT и вердикты по критериям."""
    return {
        "id": "D-%s" % str(record.id).split("-")[-1],
        "task": record.id,
        "children": [],
        "result": "",
        "implementation": [],
        "files_changed": [],
        "algorithm": [],
        "verification": [],
        "evidence": [],
        "acceptance_status": [{"id": el.get("id"), "status": "", "note": ""}
                              for el in record.elements("acceptance")],
        "attempts": [],
        "deviations": [],
        "remaining_risks": [],
        "events": [],
        "completed_at": None,
        "completed_by": None,
    }


def _write_json(path, payload):
    """Атомарная запись JSON с резервной копией: так же, как пишет ядро."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as src, \
                open(path + ".bak", "w", encoding="utf-8") as dst:
            dst.write(src.read())
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return path


def _ref_line(ref):
    if not isinstance(ref, dict):
        return str(ref)
    return "%-9s %-38s %-16s %s" % (ref.get("kind") or "-",
                                    str(ref.get("path") or "-"),
                                    str(ref.get("symbol") or "-"),
                                    ref.get("note") or "без пояснения")


def _artifact_line(art, folder):
    if not isinstance(art, dict):
        return str(art)
    path = art.get("path") or "-"
    full = path if os.path.isabs(path) else os.path.join(folder or "", path)
    size = os.path.getsize(full) if os.path.isfile(full) else 0
    return "%-8s %-24s %8d Б %s%s" % (art.get("kind") or "-", path, size,
                                      art.get("note") or "",
                                      " (производный)" if art.get("derived") else "")


def _default_mode(record, settings):
    """Состав вывода по умолчанию адаптивен: порог — настройка проекта."""
    sizes = record.sizes()
    many = int(settings.get("adaptive_comments", 10))
    chars = int(settings.get("adaptive_chars", 8000))
    if sizes["comments_count"] <= many and sizes["comments_chars"] <= chars:
        return "full"
    return "digest"


def _navigation(record):
    return ["как работать с выгрузкой:",
            "  одна реплика: ttask show %s/C-N" % record.id,
            "  один элемент: ttask show %s/AC-N" % record.id,
            "  тело отдельно: ttask show %s" % record.id,
            "  лента дословно: ttask show %s --mode comments" % record.id,
            "  дерево детей: ttask tree %s" % record.id,
            "  выгрузка устаревает при любой правке записи и пересоздаётся "
            "командой ttask digest %s" % record.id]


def _flatten(by_parent, root_id, seen=None):
    seen = seen if seen is not None else []
    for child in by_parent.get(root_id, []):
        seen.append(child.id)
        _flatten(by_parent, child.id, seen)
    return seen


def _plural(count):
    tail = abs(int(count)) % 100
    if 11 <= tail <= 14:
        return "реплик"
    digit = tail % 10
    return "реплика" if digit == 1 else ("реплики" if 2 <= digit <= 4 else "реплик")


def _op_line(op):
    if not isinstance(op, dict):
        return str(op)
    values = ", ".join("%s=%s" % (k, v) for k, v in sorted(op.items())
                       if k not in ("op", "id"))
    return "%s %s%s" % (op.get("op"), op.get("id") or "",
                        " " + values if values else "")


class _OpArgs:
    """Аргументы операции пакета: те же поля, что у флагов команды."""

    def __init__(self, op, args):
        self.__dict__.update(vars(args))
        for key, value in op.items():
            self.__dict__[str(key).replace("-", "_")] = value
        if "ids" in op and isinstance(op["ids"], list):
            self.ids = list(op["ids"])
        self.json = False
        self.quiet = True


def _op_args(op, args):
    return _OpArgs(op, args)
