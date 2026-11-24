"""Декларативные гейты закрытия: что запись обязана иметь, чтобы закрыться."""

from .errors import Issue


def close_issues(record, typedef, report=None):
    """Находки закрытия: гейты типа по фактам записи и отчёта."""
    issues = []
    gates = (typedef.gates or {}) if typedef is not None else {}
    spot = str(record.id)
    if gates.get("tests") == "required":
        if not _evidence(record, report):
            issues.append(Issue("error", spot,
                                "гейт типа требует свидетельство прогона теста",
                                "NO_TESTS"))
    if gates.get("handoff") == "required" and not record.handoffs():
        issues.append(Issue("error", "%s.comments" % spot,
                            "тип %s требует реплику пересменки" % typedef.id,
                            "NO_HANDOFF"))
    if gates.get("refs") and not record.refs:
        issues.append(Issue("error", "%s.refs" % spot,
                            "тип %s требует указатели" % typedef.id, "NO_REFS"))
    if gates.get("reproduce") and not record.extra.get("reproduce") \
            and not _text_has(record, "воспроиз"):
        issues.append(Issue("error", "%s.extra.reproduce" % spot,
                            "гейт дефекта требует воспроизведение: команда и наблюдаемое",
                            "TYPE_FIELD_MISSING"))
    if gates.get("docs") and not _docs_touched(record, report):
        issues.append(Issue("error", spot,
                            "гейт документирования: в отчёте нужен хотя бы один "
                            "изменённый файл документации", "ARTIFACT_MISSING"))
    if gates.get("acceptance") == "verdict_required" \
            and not record.extra.get("verdict"):
        issues.append(Issue("error", "%s.extra.verdict" % spot,
                            "гейт требует вердикт по критериям", "TYPE_FIELD_MISSING"))
    if report is not None:
        issues.extend(_report_issues(record, report, spot))
    return issues


def _evidence(record, report):
    if report and (report.get("evidence") or report.get("verification")):
        return True
    return any(isinstance(a, dict) and a.get("kind") in ("log", "report", "tests")
               for a in record.artifacts)


def _docs_touched(record, report):
    files = (report or {}).get("files_changed") or []
    for item in files:
        path = item.get("text") if isinstance(item, dict) else str(item)
        if path and ("docs/" in path or path.endswith(".md")):
            return True
    return False


def _text_has(record, needle):
    blob = " ".join(str(v) for v in record.data.values() if isinstance(v, str))
    return needle in blob.lower()


def _report_issues(record, report, spot):
    issues = []
    statuses = report.get("acceptance_status") or []
    covered = {el.get("id") for el in statuses if isinstance(el, dict)}
    required = {el.get("id") for el in record.elements("acceptance")}
    missing = sorted(required - covered)
    if missing:
        issues.append(Issue("error", "%s.acceptance_status" % spot,
                            "в отчёте нет вердикта по критериям %s" % ", ".join(missing),
                            "EMPTY"))
    for el in statuses:
        if isinstance(el, dict) and el.get("status") not in ("met", "not_met",
                                                             "blocked"):
            issues.append(Issue("error", "%s.acceptance_status %s"
                                % (spot, el.get("id")),
                                "вердикт — met, not_met или blocked", "KEY_UNKNOWN"))
    return issues


class Gates:
    """Декларативные гейты типа: фасад над проверкой закрытия."""

    def __init__(self, typedef):
        self.type = typedef

    def validate_close(self, record, report=None):
        return close_issues(record, self.type, report)
