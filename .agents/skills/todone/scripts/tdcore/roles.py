"""Роли и модели: `<корень>/.todone/roles.json` по схеме ROLE-1.

Идентификатор модели живёт в файле ролей проекта, а не в определении типа:
тип объявляет роль и уровень, привязку к конкретной модели делает проект.
Файл правится только командой `tcheck roles` с обязательным `--by`.
Слабейшая объявленная модель — та, на которой прогоняют маршруты фазы.
"""

import os

from . import schema
from .errors import Issue, SkillError
from .queue import ROLES_FILENAME, load_json, save_json

#: Порядок уровня от дешёвой модели к сильной.
TIER_ORDER = {"cheap": 0, "balanced": 1, "strong": 2}


class Role:
    """Роль по ROLE-1: имя, уровень, режим исполнения, инструменты, модели."""

    def __init__(self, data):
        self.data = data
        self.role = data.get("role")
        self.tier = data.get("tier")
        self.mode = data.get("mode")
        self.tools = data.get("tools")
        self.models = list(data.get("models") or [])

    def as_line(self):
        return "%-18s %-9s %-9s %-22s %s" % (
            self.role or "-", self.tier or "-", self.mode or "-",
            self.tools or "-", ", ".join(self.models) or "модель не назначена")

    def weakest_model(self):
        return self.models[0] if self.models else None

    def validate(self, issues=None):
        issues = issues if issues is not None else []
        where = "roles.%s" % (self.role or "?")
        for key in schema.ROLE_REQUIRED:
            if not self.data.get(key):
                issues.append(Issue("error", where,
                                    "обязательного поля «%s» нет" % key,
                                    "TYPE_FIELD_MISSING"))
        for key in self.data:
            if key not in schema.ROLE_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в объявлении роли", "KEY_UNKNOWN"))
        if self.tier and self.tier not in schema.TIERS:
            issues.append(Issue("error", "%s.tier" % where,
                                "уровень — cheap, balanced или strong", "KEY_UNKNOWN"))
        if self.mode and self.mode not in schema.MODES:
            issues.append(Issue("error", "%s.mode" % where,
                                "режим — inline, subagent или either", "KEY_UNKNOWN"))
        if not self.models:
            issues.append(Issue("warning", "%s.models" % where,
                                "модель не назначена: маршрут фазы не прогнать",
                                "CAPABILITY_UNBOUND"))
        return issues


class RolesIndex:
    """Индекс ролей проекта: чтение, правка командой, слабейшая модель."""

    def __init__(self, root, who=None):
        self.root = root
        self.path = os.path.join(root, ".todone", ROLES_FILENAME)
        self.who = who
        self.roles = {}
        self.by = None

    def read(self):
        data = load_json(self.path, "файл ролей") or {"version": 1, "roles": []}
        self.by = data.get("updated_by")
        self.roles = {}
        for item in data.get("roles") or []:
            role = Role(item)
            if role.role:
                self.roles[role.role] = role
        return self.roles

    def write(self):
        if not self.who:
            raise SkillError("ROLE_UNKNOWN",
                             "файл ролей правится только с именем человека",
                             self.path,
                             command="tcheck roles set <роль> --tier cheap --by <имя>")
        data = {"version": 1, "updated_by": self.who,
                "roles": [r.data for r in self.all()]}
        return save_json(self.path, data)

    def all(self):
        if not self.roles:
            self.read()
        return sorted(self.roles.values(), key=lambda r: (
            TIER_ORDER.get(r.tier, 9), r.role or ""))

    def get(self, role):
        if not self.roles:
            self.read()
        return self.roles.get(role)

    def set(self, role, who, **fields):
        """Добавить или поправить роль: правка только с именем человека."""
        self.who = who
        if not self.roles:
            self.read()
        data = dict(self.roles[role].data) if role in self.roles else {"role": role}
        data.update({k: v for k, v in fields.items() if v is not None})
        entry = Role(data)
        self.roles[role] = entry
        self.write()
        return entry

    def weakest(self):
        """Слабейшая объявленная модель: (роль, уровень, модель)."""
        for role in self.all():
            model = role.weakest_model()
            if model:
                return role, model
        return None, None

    def validate_all(self, issues=None):
        issues = issues if issues is not None else []
        for role in self.all():
            issues.extend(role.validate(issues))
        if not self.all():
            issues.append(Issue("warning", "roles",
                                "ролей не объявлено: маршруты фазы не прогнать",
                                "ROLE_UNKNOWN"))
        return issues
