"""Пакет субагенту: бриф + задача из очереди + возвратный контракт.

Субагент ничего не наследует. Пакет собирается закрытым: общий бриф
`types/_shared/subagent-brief.md` или бриф типа, объявленный в `AGENT-1.brief`,
задача из очереди в режиме `handoff` — последние K реплик и все рода `handoff`,
возвратный контракт из объявления агента. Неполный пакет — отказ
`PACK_INCOMPLETE` с печатью того, какого поля не хватает: субагент не
догадывается, он читает.
"""

import json
import os

from . import schema
from .errors import Issue, SkillError
from .report import _comment_block

DEFAULT_BRIEF = os.path.join("_shared", "subagent-brief.md")


class AgentDef:
    """Объявление субагента типа по AGENT-1."""

    def __init__(self, type_id, data, agent_id=None, folder=None):
        self.type_id = type_id
        self.data = data
        self.agent_id = agent_id or data.get("name")
        self.name = data.get("name")
        self.role = data.get("role")
        self.tools = data.get("tools")
        self.boundaries = list(data.get("boundaries") or [])
        self.contract = data.get("return_contract") or {}
        self.brief = data.get("brief") or DEFAULT_BRIEF
        self.folder = folder

    @property
    def path(self):
        if not self.folder:
            return None
        return os.path.join(self.folder, "agents", "%s.json" % self.agent_id)

    def brief_path(self, types_root):
        return os.path.join(types_root, self.brief)

    def as_line(self):
        tools = ", ".join(self.tools) if isinstance(self.tools, list) \
            else str(self.tools or "-")
        return "%-14s %-12s %-22s контракт: %s" % (
            self.agent_id, self.role or "-", tools,
            ", ".join(self.contract.get("fields") or []) or "не объявлен")

    def validate(self, issues=None):
        issues = issues if issues is not None else []
        where = "types/%s/agents/%s.json" % (self.type_id, self.agent_id)
        for key in schema.AGENT_REQUIRED:
            if not self.data.get(key):
                issues.append(Issue("error", where,
                                    "обязательного поля «%s» нет" % key,
                                    "TYPE_FIELD_MISSING"))
        for key in self.data:
            if key not in schema.AGENT_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в объявлении субагента",
                                    "KEY_UNKNOWN"))
        for key in self.contract:
            if key not in schema.RETURN_CONTRACT_KEYS:
                issues.append(Issue("error", "%s.return_contract.%s" % (where, key),
                                    "ключа нет в возвратном контракте", "KEY_UNKNOWN"))
        missing = [k for k in schema.RETURN_CONTRACT_KEYS if k not in self.contract]
        if missing:
            issues.append(Issue("error", "%s.return_contract" % where,
                                "контракт возврата неполон: нет %s"
                                % ", ".join(missing), "PACK_INCOMPLETE"))
        return issues


class Brief:
    """Сборщик пакета: один текст, который субагент получает целиком."""

    def __init__(self, types_root, settings=None):
        self.types_root = types_root
        self.settings = dict(schema.DEFAULT_SETTINGS)
        self.settings.update(settings or {})

    # --- объявления ---
    def agent(self, type_id, agent_id):
        path = os.path.join(self.types_root, type_id, "agents",
                            "%s.json" % agent_id)
        if not os.path.isfile(path):
            raise SkillError("RECORD_NOT_FOUND",
                             "объявления субагента «%s» у типа %s нет"
                             % (agent_id, type_id),
                             os.path.join(self.types_root, type_id, "agents"),
                             command="tcheck types show %s" % type_id)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return AgentDef(type_id, data, agent_id,
                        os.path.join(self.types_root, type_id))

    def agents(self, type_id):
        """Все субагенты типа: объявления из папки agents."""
        folder = os.path.join(self.types_root, type_id, "agents")
        found = []
        if not os.path.isdir(folder):
            return found
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
                data = json.load(handle)
            found.append(AgentDef(type_id, data, name[:-5],
                                  os.path.join(self.types_root, type_id)))
        return found

    def issues(self, type_id=None, issues=None):
        """Находки объявлений субагентов: одного типа или всех."""
        issues = issues if issues is not None else []
        names = [type_id] if type_id else sorted(
            d for d in os.listdir(self.types_root)
            if os.path.isdir(os.path.join(self.types_root, d))) \
            if os.path.isdir(self.types_root) else []
        for name in names:
            for agent in self.agents(name):
                issues.extend(agent.validate(issues))
        return issues

    # --- пакет ---
    def build(self, record, agent, role=None):
        """Пакет субагенту: бриф, задача, лента, контракт, границы."""
        for issue in agent.validate():
            if issue.code == "PACK_INCOMPLETE":
                raise SkillError("PACK_INCOMPLETE", issue.message, issue.where,
                                 command="tcheck types show %s" % agent.type_id)
        brief_path = agent.brief_path(self.types_root)
        if not os.path.isfile(brief_path):
            raise SkillError("PACK_INCOMPLETE",
                             "файла брифа «%s» нет: пакет субагенту собрать нельзя"
                             % agent.brief, brief_path,
                             command="tcheck types show %s" % agent.type_id)
        with open(brief_path, "r", encoding="utf-8") as handle:
            brief_text = handle.read().strip()

        lines = []
        lines.append("# Пакет субагенту %s — запись %s" % (agent.agent_id, record.id))
        lines.append("")
        lines.append("## Бриф")
        lines.append("")
        lines.append(brief_text)
        lines.append("")
        lines.append("## Задача из очереди")
        lines.append("")
        lines.append("Идентификатор %s, тип %s, статус %s, роль %s, уровень %s."
                     % (record.id, record.kind, record.status,
                        agent.role or "-", (role.tier if role else "-")))
        lines.append("Путь записи: %s" % (record.path or "-"))
        lines.append("")
        lines.append(record.body_text())
        lines.extend(self._feed_lines(record))
        lines.append("")
        lines.append("## Возвратный контракт")
        lines.append("")
        lines.extend(_contract_lines(agent.contract, record))
        lines.append("")
        lines.append("## Границы")
        lines.append("")
        if agent.boundaries:
            for item in agent.boundaries:
                lines.append("- %s" % item)
        lines.append("- тип и идентификатор записи неизменны: продолжение — "
                     "дочерняя запись;")
        lines.append("- правка записи только через CLI;")
        lines.append("- чужой факт не копируется: связь указателем "
                     "`ttask ref %s --kind queue --path <идентификатор>`;"
                     % record.id)
        lines.append("- большой вывод пишется в файл папки записи и возвращается "
                     "указателем, а не текстом.")
        return "\n".join(lines).rstrip() + "\n"

    def _feed_lines(self, record):
        """Лента в пакете: последние K реплик и все рода handoff."""
        if not record.comments:
            return ["", "Лента пуста: реплик нет."]
        last = int(self.settings.get("handoff_last", 3))
        picked, rest = record.tail(last)
        lines = ["", "## Лента: последние %d %s и все рода handoff"
                 % (last, _plural(last)), ""]
        for item in picked:
            lines.append(_comment_block(item))
            lines.append("")
        if rest > 0:
            lines.append("Не отдано %d ранних %s. Вся лента дословно: "
                         "`ttask show %s --mode comments`."
                         % (rest, _plural(rest), record.id))
        else:
            lines.append("Отдана вся лента: %d %s." % (len(picked),
                                                       _plural(len(picked))))
        return lines


def _plural(count):
    tail = abs(int(count)) % 100
    if 11 <= tail <= 14:
        return "реплик"
    digit = tail % 10
    return "реплика" if digit == 1 else ("реплики" if 2 <= digit <= 4 else "реплик")


def _contract_lines(contract, record):
    """Контракт возврата дословно: поля, форма, куда писать, что вернуть."""
    fields = contract.get("fields") or []
    lines = ["Вернуть полей: %d — %s." % (len(fields), ", ".join(fields))]
    if contract.get("shape"):
        lines.append("Состав и порядок ответа: %s" % contract["shape"])
    if contract.get("persist"):
        lines.append("Большой вывод писать в: %s" % contract["persist"])
    if contract.get("pointer"):
        lines.append("Вернуть наружу: %s" % contract["pointer"])
    lines.append("Записать результат: `ttask evidence %s --kind log --path <файл>` "
                 "или `ttask comment add %s --kind handoff --body <текст>`."
                 % (record.id, record.id))
    return lines
