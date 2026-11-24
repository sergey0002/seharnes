"""Привязки возможностей среды: `<корень>/.todone/tools.json` по схеме TOOLS-1.

Возможность объявляет тип, привязывает проект. Привязки нет — диагностика
выдаёт `CAPABILITY_UNBOUND` с двумя готовыми действиями: добавить привязку либо
идти запасным путём, объявленным в инструкции типа.
"""

import os

from . import schema
from .errors import Issue
from .queue import TOOLS_FILENAME, load_json, save_json


class ToolBinding:
    """Привязка возможности: команда или сервер, которыми она доступна."""

    def __init__(self, data):
        self.data = data
        self.capability = data.get("capability")
        self.command = data.get("command")
        self.note = data.get("note")

    def as_line(self):
        return "%-14s %-32s %s" % (self.capability or "-",
                                   self.command or "не привязана",
                                   self.note or "")

    def validate(self, issues=None):
        issues = issues if issues is not None else []
        where = "tools.%s" % (self.capability or "?")
        for key in self.data:
            if key not in schema.TOOL_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в привязке возможности",
                                    "KEY_UNKNOWN"))
        if not self.capability:
            issues.append(Issue("error", where, "имя возможности не названо",
                                "TYPE_FIELD_MISSING"))
        elif self.capability not in schema.CAPABILITIES:
            issues.append(Issue("error", where,
                                "возможности «%s» нет среди объявленных"
                                % self.capability, "CAPABILITY_UNBOUND"))
        if not self.command:
            issues.append(Issue("warning", where,
                                "команда не названа: возможность не привязана",
                                "CAPABILITY_UNBOUND"))
        return issues


class ToolsIndex:
    """Индекс привязок проекта: чтение, привязка и отвязка командой."""

    def __init__(self, root, who=None):
        self.root = root
        self.path = os.path.join(root, ".todone", TOOLS_FILENAME)
        self.who = who
        self.bindings = {}

    def read(self):
        data = load_json(self.path, "файл привязок") or {"version": 1, "tools": []}
        self.bindings = {}
        for item in data.get("tools") or []:
            binding = ToolBinding(item)
            if binding.capability:
                self.bindings[binding.capability] = binding
        return self.bindings

    def write(self):
        from .errors import SkillError
        if not self.who:
            raise SkillError("ASK_USER",
                             "привязки возможностей правятся только с именем того, "
                             "кто правит", self.path,
                             command="tcheck tools bind <возможность> "
                                     "--command <команда> --by <имя>")
        return save_json(self.path, {
            "version": 1, "updated_by": self.who,
            "tools": [b.data for b in self.all()]})

    def all(self):
        if not self.bindings:
            self.read()
        return sorted(self.bindings.values(), key=lambda b: b.capability or "")

    def get(self, capability):
        if not self.bindings:
            self.read()
        return self.bindings.get(capability)

    def bind(self, capability, command, who, note=None):
        """Привязать возможность: команда или сервер проекта."""
        self.who = who
        if not self.bindings:
            self.read()
        data = dict(self.bindings[capability].data) if capability in self.bindings \
            else {"capability": capability}
        data["command"] = command
        if note is not None:
            data["note"] = note
        binding = ToolBinding(data)
        self.bindings[capability] = binding
        self.write()
        return binding

    def unbind(self, capability, who):
        """Отвязать возможность: диагностика снова выдаст CAPABILITY_UNBOUND."""
        self.who = who
        if not self.bindings:
            self.read()
        removed = self.bindings.pop(capability, None)
        self.write()
        return removed

    def bound_issues(self, type_index, issues=None):
        """Тип объявил возможность, а привязки в проекте нет."""
        issues = issues if issues is not None else []
        if not self.bindings:
            self.read()
        for typedef in type_index.all():
            for capability in typedef.capabilities:
                binding = self.bindings.get(capability)
                if binding is None or not binding.command:
                    issues.append(Issue(
                        "error", "types/%s.capabilities" % typedef.id,
                        "тип объявил возможность «%s», а привязки в проекте нет"
                        % capability, "CAPABILITY_UNBOUND",
                        hint="добавить привязку либо идти запасным путём из "
                             "инструкции типа",
                        command="tcheck tools bind %s --command <команда> --by <имя>"
                                % capability))
        return issues

    def validate_all(self, issues=None):
        issues = issues if issues is not None else []
        for binding in self.all():
            issues.extend(binding.validate(issues))
        return issues
