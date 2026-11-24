"""Три уровня валидации: схема и факты, поля типа данными, процедурное проверкой.

Уровень третий — объявленная типом проверка — подключается в своей фазе; здесь
для него оставлено место и контракт.
"""

from .errors import Issue
from .record import validate_task


class Validator:
    """Валидатор записи: ядро плюс объявление типа."""

    def __init__(self, type_index=None, check_runner=None):
        self.types = type_index
        self.checks = check_runner

    def record(self, record, strict=True, procedural=False):
        """Все находки записи: уровни первый и второй, третий — по запросу."""
        issues = []
        typedef = None
        if self.types is not None and record.kind:
            typedef = self.types.get(record.kind) if self.types.has(record.kind) \
                else None
        issues.extend(validate_task(record, where=str(record.id), issues=[],
                                    typedef=typedef, strict=strict))
        if typedef is not None:
            issues.extend(FieldValidator(typedef).validate(record, issues=[]))
            issues.extend(self._gates(record, typedef, issues=[]))
        if procedural and self.checks is not None:
            issues.extend(self.checks.run(record, typedef))
        return issues

    def _gates(self, record, typedef, issues):
        """Гейты, которые проверяются фактами записи, а не процедурой."""
        gates = typedef.gates or {}
        spot = str(record.id)
        if record.status in ("closed",):
            if gates.get("handoff") == "required" and not record.handoffs():
                issues.append(Issue("error", "%s.comments" % spot,
                                    "тип %s требует реплику пересменки перед закрытием"
                                    % typedef.id, "NO_HANDOFF"))
            if gates.get("refs") and not record.refs:
                issues.append(Issue("error", "%s.refs" % spot,
                                    "тип %s требует указатели на файлы, символы или "
                                    "документацию" % typedef.id, "NO_REFS"))
            if gates.get("tests") == "required" and not _has_evidence(record):
                issues.append(Issue("error", "%s.evidence" % spot,
                                    "гейт типа требует свидетельство прогона теста",
                                    "NO_TESTS"))
        if record.source is not None:
            raw = (record.source or {}).get("raw")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                issues.append(Issue("error", "%s.source.raw" % spot,
                                    "зеркало обязано хранить содержимое дословно",
                                    "SOURCE_RAW_MISSING"))
        return issues


def _has_evidence(record):
    for art in record.artifacts:
        if isinstance(art, dict) and art.get("kind") in ("log", "report", "tests"):
            return True
    for ref in record.refs:
        if isinstance(ref, dict) and ref.get("kind") == "report":
            return True
    return bool(record.extra.get("evidence"))


class FieldValidator:
    """Второй уровень валидатора: дополнительные поля только данными типа."""

    def __init__(self, typedef):
        self.type = typedef

    def validate(self, record, issues=None):
        """Проверить `extra`: неизвестное, обязательное, тип, enum, pattern."""
        return self.type.validate_extra(record, issues=issues)
