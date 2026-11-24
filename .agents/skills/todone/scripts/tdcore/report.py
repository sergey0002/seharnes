"""Печать (Reporter): одна строка на объект, положение дел, режимы чтения, срез для машины.

Ни один режим чтения не обрезает текст. Размеры печатаются в знаках и байтах,
токенов в размерах нет: токенизатор был бы ещё одной зависимостью.
"""

import json

from . import schema
from .errors import SkillError

#: Режимы чтения записи: девять. Пакет субагенту собирается своей командой.
READ_MODES = ("body", "full", "comments", "digest", "handoff", "comment",
              "element", "report", "pack")
#: Режимы, которые отдаёт команда чтения записи: восемь, без пакета.
SHOW_MODES = tuple(m for m in READ_MODES if m != "pack")
#: Режимы ленты, в которых пакет субагенту отдаёт реплики.
PACK_MODES = ("handoff", "digest", "comments", "full")


def plural(count, one, few, many):
    """Форма существительного по числу: вывод читает человек."""
    tail = abs(int(count)) % 100
    if 11 <= tail <= 14:
        return many
    digit = tail % 10
    if digit == 1:
        return one
    if 2 <= digit <= 4:
        return few
    return many


def record_line(row):
    """Строка записи в фиксированном порядке полей, без украшений."""
    priority = row.get("priority")
    parts = [
        str(row.get("id") or "-"),
        str(row.get("type") or "-"),
        str(row.get("status") or "-"),
        "p%s" % priority if isinstance(priority, int) else "p-",
        str(row.get("phase") or "-"),
        "«%s»" % (row.get("title") or ""),
        str(row.get("path") or "-"),
    ]
    return " ".join(parts)


def state_line(counts, next_action=None):
    """Положение дел и следующее действие: завершает каждый вывод."""
    parts = ["всего %d" % counts.get("all", 0)]
    for key, label in (("in_progress", "в работе"), ("ready", "готово"),
                       ("blocked", "заблокировано"), ("draft", "черновиков"),
                       ("parked", "отложено"), ("mirror", "зеркал"),
                       ("closed", "закрыто")):
        if counts.get(key):
            parts.append("%s %d" % (label, counts[key]))
    line = "состояние: " + " | ".join(parts)
    if next_action:
        line += " | next: " + next_action
    return line


def sizes_line(sizes, note=None):
    """Размеры в знаках и байтах: факты для решения, что читать дальше."""
    line = ("размеры: тело %d зн. / %d Б, лента %d зн. / %d Б, реплик %d"
            % (sizes["body_chars"], sizes["body_bytes"], sizes["comments_chars"],
               sizes["comments_bytes"], sizes["comments_count"]))
    if note:
        line += " | " + note
    return line


def emit(lines, stream, json_obj=None, fields=None, quiet=False, limit=None):
    """Печать вывода с добровольными срезами: --json, --fields, --quiet, --limit."""
    if json_obj is not None:
        stream.write(json.dumps(json_obj, ensure_ascii=False, indent=2) + "\n")
        return 0
    if quiet:
        return 0
    printed = 0
    for line in lines:
        if limit is not None and printed >= limit and line.startswith("состояние:"):
            stream.write("состояние: напечатано %d строк из %d, остальные — без --limit\n"
                         % (printed, len(lines)))
            break
        if fields and line and not line.startswith(("состояние:", "размеры:")):
            line = _slice_fields(line, fields)
        stream.write(line + "\n")
        printed += 1
    return printed


def _slice_fields(line, fields):
    """Срез --fields: позиции строки записи в фиксированном порядке."""
    order = ("id", "type", "status", "priority", "phase", "title", "path")
    parts = line.split(" ", 6)
    picked = []
    for name in fields:
        if name in order and order.index(name) < len(parts):
            picked.append(parts[order.index(name)])
    return " ".join(picked) if picked else line


def render_show(record, mode="body", address=None, settings=None, typedef=None):
    """Вывод чтения записи в названном режиме: ничего не режется.

    Возвращает список строк. Режимы: тело, тело с лентой, только лента,
    оглавление ленты, хвост ленты, одна реплика, один элемент, отчёт.
    """
    settings = settings or schema.DEFAULT_SETTINGS
    if mode == "pack":
        raise SkillError("READ_MODE_UNKNOWN",
                         "пакет субагенту режимом чтения не отдаётся",
                         "ttask show %s" % record.id,
                         hint="пакет собирается одной командой",
                         command="ttask pack %s" % record.id)
    if mode not in SHOW_MODES:
        raise SkillError("READ_MODE_UNKNOWN",
                         "режим «%s» неизвестен" % mode,
                         "ttask show %s" % record.id,
                         hint="режим чтения — %s" % ", ".join(SHOW_MODES),
                         command="ttask show %s --mode %s"
                                 % (record.id, "|".join(SHOW_MODES)))
    sizes = record.sizes()
    lines = []
    note = None

    if mode in ("body", "full", "digest", "handoff", "pack"):
        lines.append(record.body_text())
    if mode == "full":
        lines.append("")
        lines.append("лента (%d реплик):" % sizes["comments_count"])
        for item in record.comments:
            lines.append(_comment_block(item))
    if mode == "comments":
        lines.append("лента (%d реплик):" % sizes["comments_count"])
        for item in record.comments:
            lines.append(_comment_block(item))
    if mode == "digest":
        lines.append("")
        lines.append("оглавление ленты:")
        for item in record.comments:
            lines.append(record.toc_line(item))
        note = "лента дословно: ttask show %s --mode comments" % record.id
    if mode == "handoff":
        last = int(settings.get("handoff_last", 3))
        picked, rest = record.tail(last)
        lines.append("")
        lines.append("хвост ленты: последние %d %s и все рода handoff"
                     % (last, plural(last, "реплика", "реплики", "реплик")))
        for item in picked:
            lines.append(_comment_block(item))
        if rest > 0:
            note = ("отдано %d %s, осталось %d: ttask show %s --mode comments"
                    % (len(picked), plural(len(picked), "реплика", "реплики",
                                           "реплик"), rest, record.id))
        else:
            note = "отдана вся лента: %d %s" % (
                len(picked), plural(len(picked), "реплика", "реплики", "реплик"))
    if mode == "comment":
        item = record.comment(address)
        if item is None:
            raise SkillError("RECORD_NOT_FOUND",
                             "реплики %s в ленте записи нет" % address, record.id,
                             command="ttask show %s --mode digest" % record.id)
        lines = [_comment_block(item)]
        note = "вся лента: ttask show %s --mode comments" % record.id
    if mode == "element":
        field, element = record.element(address)
        if element is None:
            raise SkillError("RECORD_NOT_FOUND",
                             "элемента %s в записи нет" % address, record.id,
                             command="ttask show %s" % record.id)
        lines = ["%s %s: %s" % (field, element.get("id"), element.get("text"))]
        note = "вся запись: ttask show %s" % record.id
    if mode == "report":
        lines.append(json.dumps(record.data.get("report") or {},
                                ensure_ascii=False, indent=2))

    lines.append("")
    lines.append(sizes_line(sizes, note))
    lines.extend(_digest_offer(record, sizes, settings))
    return lines


def _digest_offer(record, sizes, settings):
    """Предложение выгрузки при большом теле или ленте: добавляется к полному выводу."""
    threshold = int(settings.get("digest_chars", 40000))
    total = sizes["body_chars"] + sizes["comments_chars"]
    if total < threshold:
        return []
    return [
        "выгрузка: тело %d зн., лента %d зн. — выгрузить для чтения: ttask digest %s"
        % (sizes["body_chars"], sizes["comments_chars"], record.id),
        "как работать с выгрузкой: одна реплика ttask show %s/C-N, один элемент "
        "ttask show %s/AC-N, тело ttask show %s, лента ttask show %s --mode comments, "
        "дерево детей ttask tree %s; часть выгрузки ttask digest %s --part body|toc|comments"
        % (record.id, record.id, record.id, record.id, record.id, record.id),
        "файл выгрузки производный: устаревает при любой правке записи и "
        "пересоздаётся той же командой",
    ]


def _comment_block(item):
    """Реплика дословно: идентификатор, время, автор, род и весь текст."""
    return "%s %s %s %s\n%s" % (item.get("id"), item.get("at"), item.get("by"),
                                item.get("kind"), item.get("text"))


def render_tree(record, rows_by_parent, indent=0, lines=None):
    """Дерево записи: по строке на потомка — что каждый оставил."""
    lines = lines if lines is not None else []
    prefix = "   " * indent + ("└─ " if indent else "")
    summary = _left_behind(record)
    lines.append("%s%s  %-11s %-11s %s" % (prefix, record.id, record.kind,
                                            record.status, summary))
    for child in rows_by_parent.get(record.id, []):
        render_tree(child, rows_by_parent, indent + 1, lines)
    return lines


def _left_behind(record):
    """Что запись оставила: указатели, артефакты, реплика пересменки."""
    parts = []
    if record.refs:
        parts.append("refs×%d" % len(record.refs))
    if record.artifacts:
        parts.append("артефактов×%d" % len(record.artifacts))
    if record.handoffs():
        parts.append("handoff C-%s" % record.handoffs()[-1].get("id", "")[2:])
    if record.extra:
        parts.append("extra×%d" % len(record.extra))
    return "оставил: " + ", ".join(parts) if parts else "ничего не оставил"


class Reporter:
    """Печать общего контракта: строка на объект, режимы чтения, состояние."""

    read_modes = READ_MODES

    @staticmethod
    def record_line(row):
        return record_line(row)

    @staticmethod
    def state_line(counts, next_action=None):
        return state_line(counts, next_action)

    @staticmethod
    def show(record, mode="body", address=None, settings=None):
        return render_show(record, mode, address, settings)

    @staticmethod
    def tree(record, rows_by_parent):
        return render_tree(record, rows_by_parent)
