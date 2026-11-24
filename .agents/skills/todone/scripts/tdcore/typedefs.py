"""Тип задачи как данные: состав полей, гейты, исполнитель, возможности, проверки.

В этой фазе типы поставляются встроенной таблицей; папка плагина
`types/<имя>/type.json` читается тем же кодом и перекрывает встроенное
объявление. Профиль типа и проверки — следующие фазы.
"""

import json
import os

from . import schema
from .errors import Issue, SkillError

GATE_KEYS = ("tests", "evidence", "handoff", "reproduce", "docs", "close",
             "acceptance", "acceptance_min", "acceptance_style", "refs",
             "change_kind_required", "out_of_scope_required")


def _field(name, ftype, required, message, example, enum=None, pattern=None):
    return {"name": name, "type": ftype, "required": required, "enum": enum,
            "pattern": pattern, "message": message, "example": example}


#: Встроенные объявления типов. Данные, а не код.
BUILTIN = {
    "default": {
        "id": "default", "name": "Работа без особой формы", "class": "product",
        "gates": {"tests": "not_required", "acceptance_min": 2,
                  "change_kind_required": True, "close": "work"},
        "fields": [],
    },
    "mirror": {
        "id": "mirror", "name": "Зеркало внешней системы", "class": "source",
        "editor": "import_only",
        "gates": {"tests": "not_required", "acceptance_min": False,
                  "close": "none"},
        "fields": [_field("mirror_note", "string", False,
                          "что известно о снимке: что изменилось с прошлой загрузки",
                          "повторный импорт 14.11: добавлены два комментария")],
    },
    "intake": {
        "id": "intake", "name": "Формализация стадии", "class": "research",
        "gates": {"tests": "not_required", "handoff": "required",
                  "acceptance_min": False, "close": "result_is_knowledge"},
        "capabilities": ["code-graph", "memory"],
        "fields": [
            _field("raw_gaps", "string", True,
                   "чего не хватает в сыром тексте и что неясно: перечнем",
                   "не назван срок; неясно, кто принимает; нет критериев"),
            _field("assumptions", "string", True,
                   "какие допущения приняты и почему они безопасны",
                   "принимаем, что экспорт остаётся в прежнем формате"),
            _field("draft_child", "string", True,
                   "черновик рабочей записи: тип, заголовок, цель из сырого текста",
                   "planning «План реализации переноса экспорта»"),
        ],
    },
    "planning": {
        "id": "planning", "name": "План реализации", "class": "research",
        "gates": {"tests": "not_required", "acceptance_min": 2,
                  "close": "result_is_knowledge"},
        "fields": [
            _field("approach", "string", True,
                   "чем меняем: способ, затронутые модули, отвергнутые варианты и причина",
                   "меняем модуль экспорта; вариант с новым сервисом отклонён: нужен один процесс"),
            _field("changes", "string", True,
                   "что меняем: на каждый пункт файл, символ, текущее и новое поведение",
                   "scripts/export.py: build_rows — сейчас возвращает список, будет возвращать итератор"),
            _field("outcome", "string", True,
                   "что получим: наблюдаемое поведение, а не перечень правок",
                   "большой экспорт сохраняет приемлемое время выполнения"),
            _field("check", "string", True,
                   "как проверить: команда и ожидаемый вывод",
                   "python3 -m unittest tests.test_export — OK, 12 тестов"),
        ],
    },
    "research": {
        "id": "research", "name": "Исследование кода и документации",
        "class": "research",
        "gates": {"tests": "not_required", "handoff": "required",
                  "acceptance_min": False, "close": "result_is_knowledge",
                  "refs": True},
        "capabilities": ["code-graph", "memory"],
        "fields": [],
    },
    "libs-research": {
        "id": "libs-research", "name": "Поиск готовых библиотек",
        "class": "research",
        "gates": {"tests": "not_required", "handoff": "required",
                  "acceptance_min": False, "close": "result_is_knowledge"},
        "capabilities": ["web-search"],
        "fields": [
            _field("candidates", "string", True,
                   "кандидаты: что нашли и где", "openpyxl, xlsxwriter, pandas"),
            _field("comparison", "string", True,
                   "сравнение по тому, что важно проекту",
                   "openpyxl: только стандартная установка не нужна; xlsxwriter: пишет быстрее"),
            _field("verdict", "string", True,
                   "вердикт и причина", "берём xlsxwriter: запись быстрее, лицензия BSD"),
        ],
    },
    "feature": {
        "id": "feature", "name": "Новая возможность", "class": "product",
        "gates": {"tests": "required", "evidence": True, "acceptance_min": 2,
                  "change_kind_required": True, "docs": True, "close": "work"},
        "fields": [],
    },
    "fix": {
        "id": "fix", "name": "Дефект", "class": "product",
        "gates": {"tests": "required", "evidence": True, "reproduce": True,
                  "acceptance_min": 2, "change_kind_required": True,
                  "close": "work"},
        "fields": [_field("reproduce", "string", True,
                          "как воспроизвести дефект: команда и наблюдаемое поведение",
                          "python -m unittest tests.test_x — получаем ValueError")],
    },
    "small-fix": {
        "id": "small-fix", "name": "Мелкая правка", "class": "product",
        "gates": {"tests": "not_required", "acceptance_min": 2,
                  "change_kind_required": True, "close": "work"},
        "fields": [_field("why_no_test", "string", True,
                          "почему тест не нужен: что именно не меняется в поведении",
                          "опечатка в строке подсказки, поведение команды не меняется")],
    },
    "test-prep": {
        "id": "test-prep", "name": "Тексты тестов до реализации",
        "class": "product",
        "executor": {"role": "tester", "tier": "balanced", "mode": "subagent"},
        "gates": {"tests": "not_required", "handoff": "required",
                  "acceptance_min": False, "close": "work"},
        "fields": [],
    },
    "testing": {
        "id": "testing", "name": "Прогон тестов и вердикт", "class": "product",
        "executor": {"role": "tester", "tier": "balanced", "mode": "subagent"},
        "gates": {"tests": "required", "evidence": True,
                  "acceptance": "verdict_required", "acceptance_min": False,
                  "close": "work"},
        "capabilities": ["test-runner"],
        "fields": [_field("verdict", "string", True,
                          "вердикт по критериям: met, not_met или blocked на каждый",
                          "AC-1 met, AC-2 met, AC-3 blocked: нет доступа к сети")],
    },
    "code-review": {
        "id": "code-review", "name": "Разбор изменения и диффа",
        "class": "product",
        "executor": {"role": "reviewer", "tier": "balanced", "mode": "subagent"},
        "gates": {"tests": "not_required", "evidence": True,
                  "acceptance_min": False, "close": "work"},
        "capabilities": ["git", "code-graph"],
        "fields": [_field("verdict", "string", True,
                          "вердикт разбора: принимать, принимать с правками, отклонить",
                          "принимать с правками: два замечания по именам")],
    },
    "doc": {
        "id": "doc", "name": "Документация продукта", "class": "product",
        "gates": {"tests": "not_required", "docs": True, "acceptance_min": False,
                  "close": "docs_rendered"},
        "capabilities": ["docs-store"],
        "fields": [],
    },
}


class TypeDef:
    """Тип как данные: поля, гейты, исполнитель, возможности, проверки, редактор."""

    __slots__ = ("data", "folder")

    def __init__(self, data, folder=None):
        self.data = data
        self.folder = folder

    @property
    def id(self):
        return self.data.get("id")

    @property
    def name(self):
        return self.data.get("name") or self.id

    @property
    def klass(self):
        return self.data.get("class") or "product"

    @property
    def gates(self):
        return self.data.get("gates") or {}

    @property
    def fields(self):
        return [f for f in (self.data.get("fields") or []) if isinstance(f, dict)]

    @property
    def capabilities(self):
        return self.data.get("capabilities") or []

    @property
    def checks(self):
        return self.data.get("checks") or []

    @property
    def editor(self):
        return self.data.get("editor") or "any"

    @property
    def profile(self):
        return self.data.get("profile")

    @property
    def executor(self):
        return self.data.get("executor")

    @property
    def stages(self):
        return self.data.get("stages") or []

    def as_line(self):
        """Строка типа в справке: имя, класс, гейты, редактор, поля."""
        gates = ", ".join("%s=%s" % (k, v) for k, v in sorted(self.gates.items()))
        return "%-14s %-9s %-9s %-34s полей: %d%s" % (
            self.id, self.klass, self.editor, gates or "-", len(self.fields),
            ", возможностей: " + ", ".join(self.capabilities)
            if self.capabilities else "")

    def field(self, name):
        for item in self.fields:
            if item.get("name") == name:
                return item
        return None

    def required_fields(self):
        return [f for f in self.fields if f.get("required")]

    def validate(self, issues=None):
        """Проверка объявления типа: схема TYPE-5, без числовых критериев."""
        issues = issues if issues is not None else []
        spot = "тип %s" % self.id
        allowed = schema.TYPE_KEYS + schema.TYPE_PLUGIN_KEYS + ("gates.tests",)
        for key in self.data:
            if key not in allowed:
                issues.append(Issue("error", spot,
                                    "ключ «%s» не из схемы TYPE-5" % key,
                                    "KEY_UNKNOWN"))
        if self.editor not in schema.EDITORS:
            issues.append(Issue("error", "%s.editor" % spot,
                                "редактор «%s» не из %s" % (self.editor,
                                                            list(schema.EDITORS)),
                                "KEY_UNKNOWN"))
        if self.klass not in schema.CLASSES:
            issues.append(Issue("warning", "%s.class" % spot,
                                "класс «%s» не из %s" % (self.klass,
                                                         list(schema.CLASSES)),
                                "KEY_UNKNOWN"))
        for key in self.gates:
            if key not in GATE_KEYS:
                issues.append(Issue("error", "%s.gates" % spot,
                                    "гейт «%s» не объявлен" % key, "KEY_UNKNOWN"))
        for cap in self.capabilities:
            if cap not in schema.CAPABILITIES:
                issues.append(Issue("error", "%s.capabilities" % spot,
                                    "возможность «%s» не объявлена" % cap,
                                    "KEY_UNKNOWN"))
        for field in self.fields:
            issues.extend(self._validate_field(field, spot))
        for check in self.checks:
            for key in check:
                if key not in schema.CHECK_KEYS:
                    issues.append(Issue("error", "%s.checks" % spot,
                                        "ключ «%s» не из CHECK-1" % key,
                                        "KEY_UNKNOWN"))
        return issues

    def _validate_field(self, field, spot):
        issues = []
        place = "%s.fields.%s" % (spot, field.get("name"))
        for key in field:
            if key not in schema.FIELD_KEYS:
                issues.append(Issue("error", place,
                                    "ключ «%s» не из FIELD-1" % key, "KEY_UNKNOWN"))
        if field.get("type") not in schema.FIELD_TYPES:
            issues.append(Issue("error", place,
                                "тип поля «%s» не из %s" % (field.get("type"),
                                                            list(schema.FIELD_TYPES)),
                                "KEY_UNKNOWN"))
        if not isinstance(field.get("message"), str) or not field["message"].strip():
            issues.append(Issue("error", place,
                                "у поля нет текста требования: отказ нечем пояснить",
                                "EMPTY"))
        if not isinstance(field.get("example"), str) or not field["example"].strip():
            issues.append(Issue("error", place,
                                "у поля нет образца: слабая модель не знает, как писать",
                                "EMPTY"))
        for banned in ("min_chars", "max_chars", "min_items", "max_len"):
            if banned in field:
                issues.append(Issue("error", place,
                                    "числовой критерий «%s» запрещён: достаточность текста "
                                    "объявляется словами" % banned, "TYPE_FIELD_INVALID"))
        return issues

    def validate_extra(self, record, issues=None):
        """Уровень второй: дополнительные поля по объявлению типа, данными."""
        issues = issues if issues is not None else []
        extra = record.data.get("extra") or {}
        spot = str(record.id)
        if not isinstance(extra, dict):
            issues.append(Issue("error", "%s.extra" % spot,
                                "extra — объект с именами, объявленными типом",
                                "KEY_UNKNOWN"))
            return issues
        declared = {f.get("name") for f in self.fields}
        for name, value in extra.items():
            if name not in declared:
                issues.append(Issue("error", "%s.extra.%s" % (spot, name),
                                    "тип %s не объявляет такого поля" % self.id,
                                    "TYPE_FIELD_UNKNOWN"))
                continue
            field = self.field(name)
            issues.extend(self._check_value(field, value, spot))
        for field in self.required_fields():
            name = field.get("name")
            value = extra.get(name)
            if value is None or (isinstance(value, str) and not value.strip()) \
                    or (isinstance(value, (list, dict)) and not value):
                issues.append(Issue("error", "%s.extra.%s" % (spot, name),
                                    "тип %s требует текст: %s → образец: %s"
                                    % (self.id, field.get("message"),
                                       field.get("example")),
                                    "TYPE_FIELD_MISSING"))
        return issues

    def _check_value(self, field, value, spot):
        issues = []
        place = "%s.extra.%s" % (spot, field.get("name"))
        expected = field.get("type")
        ok = {
            "string": lambda v: isinstance(v, str),
            "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "bool": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }.get(expected, lambda v: True)
        if not ok(value):
            issues.append(Issue("error", place,
                                "значение типа %s, а объявлен %s"
                                % (type(value).__name__, expected),
                                "TYPE_FIELD_INVALID"))
            return issues
        enum = field.get("enum")
        if enum and value not in enum:
            issues.append(Issue("error", place,
                                "значение «%s» не из перечня %s" % (value, list(enum)),
                                "TYPE_FIELD_INVALID"))
        pattern = field.get("pattern")
        if pattern and isinstance(value, str):
            import re
            if not re.match(pattern, value):
                issues.append(Issue("error", place,
                                    "значение «%s» не в формате %s" % (value, pattern),
                                    "TYPE_FIELD_INVALID"))
        return issues


class TypeIndex:
    """Поиск и разрешение типов: встроенные плюс папки плагинов проекта."""

    def __init__(self, folders=None):
        if isinstance(folders, str):
            folders = [folders]
        self.folders = [f for f in (folders or []) if f]
        self._defs = {}

    def _builtin(self):
        if not self._defs:
            for name, data in BUILTIN.items():
                self._defs[name] = TypeDef(dict(data))
            for folder in self.folders:
                self._load_folder(folder)
        return self._defs

    def _load_folder(self, folder):
        if not os.path.isdir(folder):
            return
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, "type.json")
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except ValueError as exc:
                raise SkillError("JSON_MALFORMED",
                                 "конфиг типа не разбирается как JSON: %s" % exc, path)
            if not isinstance(data, dict):
                raise SkillError("JSON_MALFORMED", "конфиг типа должен быть объектом",
                                 path)
            data.setdefault("id", name)
            merged = dict(BUILTIN.get(data["id"], {}))
            merged.update(data)
            self._defs[merged["id"]] = TypeDef(merged, folder=os.path.join(folder, name))

    def names(self):
        return sorted(self._builtin())

    def get(self, kind):
        defs = self._builtin()
        if kind not in defs:
            raise SkillError("TYPE_UNKNOWN",
                             "тип «%s» не объявлен: ни в поставке, ни в папке типов" % kind,
                             "tcheck types list")
        return defs[kind]

    def has(self, kind):
        return kind in self._builtin()

    def all(self):
        return [self._builtin()[name] for name in self.names()]

    def validate_all(self):
        issues = []
        for typedef in self.all():
            issues.extend(typedef.validate())
        return issues

    def codes(self):
        """Коды, объявленные типами: сливаются с таблицей диагностики."""
        out = {}
        for typedef in self.all():
            for check in typedef.checks:
                for code in check.get("codes") or []:
                    if isinstance(code, dict) and code.get("id"):
                        out[code["id"]] = (code.get("hint") or "", "")
        return out
