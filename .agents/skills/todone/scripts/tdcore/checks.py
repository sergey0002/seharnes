"""Проверка-плагин: объявление CHECK-1, загрузка, контракт входа и выхода.

Код плагина не исполняется при чтении или проверке записи: запуск только по
явной команде. Контракт — вход (путь записи и объект записи), выход (JSON с
ключами `ok`, `findings`, `summary`), коды возврата 0, 1 и 3.
"""

import importlib.util
import json
import os
import subprocess
import sys

from . import schema
from .errors import EXIT_ASK_USER, EXIT_FINDINGS, EXIT_OK, Issue, SkillError

#: Ключи ответа проверки: контракт, который проверяет ядро.
RESULT_KEYS = ("ok", "findings", "summary")
FINDING_KEYS = ("level", "where", "message", "code")


class CheckPlugin:
    """Базовый класс проверки типа: потомок живёт в `types/<тип>/checks/`."""

    #: Коды, которые проверка вправе вернуть: объявляются в конфиге типа.
    codes = ()

    def __init__(self, typedef=None):
        self.type = typedef

    def run(self, path, record):
        """Проверить запись: вернуть словарь по контракту RESULT_KEYS."""
        raise NotImplementedError("проверка обязана определить метод run")

    def as_result(self, ok, findings=None, summary=""):
        return {"ok": bool(ok), "findings": list(findings or []),
                "summary": summary}

    def findings_to_issues(self, result):
        """Находки проверки в общие находки ядра: коды сверяются с объявлением."""
        issues = []
        declared = set(self.codes or ())
        code_hints = {}
        if self.type is not None:
            for declaration in self.type.checks or ():
                for code in declaration.get("codes") or ():
                    if isinstance(code, dict) and code.get("id"):
                        code_hints[code["id"]] = code.get("hint") or ""
        for item in result.get("findings") or []:
            if not isinstance(item, dict):
                issues.append(Issue("error", "check %s" % type(self).__name__,
                                    "находка проверки не объект", "CHECK_CONTRACT"))
                continue
            code = item.get("code")
            if code and declared and code not in declared:
                issues.append(Issue("error", "check %s" % type(self).__name__,
                                    "код «%s» не объявлен типом" % code,
                                    "CHECK_CONTRACT"))
                continue
            issues.append(Issue(item.get("level") or "error",
                                item.get("where") or "-",
                                item.get("message") or "находка без сообщения",
                                code,
                                hint=code_hints.get(code) or None,
                                command="tcheck types show %s"
                                        % self.type.id if self.type is not None else None))
        return issues


class CheckRunner:
    """Запуск объявленных типом проверок: загрузка, контракт, коды."""

    def __init__(self, types_root):
        self.types_root = types_root

    def declared(self, typedef):
        return list((typedef.checks or []) if typedef else [])

    def load(self, typedef, check):
        """Загрузить класс проверки по объявлению CHECK-1."""
        module_name = check.get("module")
        class_name = check.get("class")
        if not module_name or not class_name:
            raise SkillError("CHECK_LOAD_FAILED",
                             "объявление проверки без модуля или класса",
                             "types/%s/type.json" % typedef.id,
                             command="tcheck types show %s" % typedef.id)
        relative = module_name if str(module_name).endswith(".py") \
            else "%s.py" % module_name
        if relative.startswith("checks/"):
            path = os.path.join(self.types_root, typedef.id, relative)
        else:
            path = os.path.join(self.types_root, typedef.id, "checks", relative)
        path = os.path.abspath(path)
        type_folder = os.path.abspath(os.path.join(self.types_root, typedef.id))
        if not path.startswith(type_folder + os.sep):
            raise SkillError("CHECK_LOAD_FAILED",
                             "путь проверки выходит из папки типа", path,
                             command="tcheck types show %s" % typedef.id)
        if not os.path.isfile(path):
            raise SkillError("CHECK_LOAD_FAILED",
                             "модуля проверки «%s» нет" % module_name, path,
                             command="tcheck types show %s" % typedef.id)
        spec = importlib.util.spec_from_file_location(
            "tdcore_check_%s_%s" % (typedef.id.replace("-", "_"),
                                    check.get("id") or "check"), path)
        if spec is None or spec.loader is None:
            raise SkillError("CHECK_LOAD_FAILED",
                             "модуль проверки «%s» не загружается" % module_name,
                             path, command="tcheck types show %s" % typedef.id)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            raise SkillError("CHECK_LOAD_FAILED",
                             "модуль проверки «%s» упал при загрузке: %s"
                             % (module_name, exc), path,
                             command="tcheck types show %s" % typedef.id)
        klass = getattr(module, class_name, None)
        if klass is None or not (isinstance(klass, type)
                                 and issubclass(klass, CheckPlugin)):
            raise SkillError("CHECK_LOAD_FAILED",
                             "класса «%s» потомка CheckPlugin в модуле нет"
                             % class_name, path,
                             command="tcheck types show %s" % typedef.id)
        plugin = klass(typedef)
        declared_codes = []
        for item in check.get("codes") or plugin.codes or ():
            declared_codes.append(item.get("id") if isinstance(item, dict) else item)
        plugin.codes = tuple(code for code in declared_codes if code)
        return plugin

    def run(self, record, typedef, when=None):
        """Запустить проверки записи: только явным вызовом, не при чтении."""
        issues = []
        for check in self.declared(typedef):
            if when and check.get("when") and check.get("when") != when:
                continue
            plugin = self.load(typedef, check)
            result = plugin.run(record.path, record)
            issues.extend(self._contract(record, check, plugin, result))
        return issues

    def _contract(self, record, check, plugin, result):
        """Сверить ответ проверки с контрактом: ключи, типы, коды."""
        where = "types/%s/checks:%s" % (plugin.type.id if plugin.type else "-",
                                        check.get("id"))
        if not isinstance(result, dict):
            return [Issue("error", where,
                          "проверка вернула не объект JSON", "CHECK_CONTRACT")]
        issues = []
        for key in RESULT_KEYS:
            if key not in result:
                issues.append(Issue("error", where,
                                    "в ответе проверки нет ключа «%s»" % key,
                                    "CHECK_CONTRACT"))
        for key in result:
            if key not in RESULT_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в контракте проверки",
                                    "CHECK_CONTRACT"))
        if "ok" in result and not isinstance(result["ok"], bool):
            issues.append(Issue("error", "%s.ok" % where,
                                "признак успеха — true или false",
                                "CHECK_CONTRACT"))
        for item in result.get("findings") or []:
            if not isinstance(item, dict):
                issues.append(Issue("error", "%s.findings" % where,
                                    "находка проверки не объект",
                                    "CHECK_CONTRACT"))
                continue
            for key in item:
                if key not in FINDING_KEYS:
                    issues.append(Issue("error", "%s.findings.%s" % (where, key),
                                        "ключа нет в находке проверки",
                                        "CHECK_CONTRACT"))
        issues.extend(plugin.findings_to_issues(result))
        return issues

    def run_external(self, argv, cwd=None):
        """Прогон проверки отдельным процессом: коды возврата 0, 1 и 3."""
        try:
            done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                  check=False)
        except OSError as exc:
            raise SkillError("CHECK_LOAD_FAILED",
                             "проверку не запустить: %s" % exc, " ".join(argv),
                             command="tcheck selftest")
        code = done.returncode
        if code not in (EXIT_OK, EXIT_FINDINGS, EXIT_ASK_USER):
            raise SkillError("CHECK_CONTRACT",
                             "проверка вернула код %d: договорены 0, 1 и 3" % code,
                             " ".join(argv), command="tcheck selftest")
        try:
            payload = json.loads(done.stdout or "{}")
        except ValueError:
            raise SkillError("CHECK_CONTRACT",
                             "проверка напечатала не JSON", " ".join(argv),
                             command="tcheck selftest")
        return code, payload, done.stderr

    def validate_declarations(self, typedef, issues=None):
        """Находки объявлений проверок типа: схема CHECK-1 и коды CODE-1."""
        issues = issues if issues is not None else []
        where = "types/%s/type.json" % typedef.id
        for pos, check in enumerate(self.declared(typedef)):
            spot = "%s.checks[%d]" % (where, pos)
            if not isinstance(check, dict):
                issues.append(Issue("error", spot, "объявление проверки не объект",
                                    "KEY_UNKNOWN"))
                continue
            for key in check:
                if key not in schema.CHECK_KEYS:
                    issues.append(Issue("error", "%s.%s" % (spot, key),
                                        "ключа нет в объявлении проверки",
                                        "KEY_UNKNOWN"))
            for key in ("id", "module", "class"):
                if not check.get(key):
                    issues.append(Issue("error", spot,
                                        "обязательного поля «%s» нет" % key,
                                        "TYPE_FIELD_MISSING"))
            if check.get("when") and check["when"] not in schema.CHECK_WHEN:
                issues.append(Issue("error", "%s.when" % spot,
                                    "момент запуска — on_close, on_evidence или "
                                    "on_demand", "KEY_UNKNOWN"))
            for code in check.get("codes") or []:
                if not isinstance(code, dict):
                    issues.append(Issue("error", "%s.codes" % spot,
                                        "объявление кода не объект", "KEY_UNKNOWN"))
                    continue
                for key in code:
                    if key not in schema.CODE_KEYS:
                        issues.append(Issue("error", "%s.codes.%s" % (spot, key),
                                            "ключа нет в объявлении кода",
                                            "KEY_UNKNOWN"))
                if code.get("level") and code["level"] not in schema.CODE_LEVELS:
                    issues.append(Issue("error", "%s.codes.%s"
                                        % (spot, code.get("id")),
                                        "уровень кода — error или warning",
                                        "KEY_UNKNOWN"))
        return issues
