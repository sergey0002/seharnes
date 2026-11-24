"""Точка входа `tqueue`: очередь как порядок.

Состав команд: найти очереди, создать очередь, список с отбором, следующая
работа, положение дел, история закрытых, порядок, полосы сроков, доска одним
вызовом, пересборка индекса. Запись как работа — в `ttask`, контроль и типы —
в `tcheck`.
"""

from .cli import Cli, Command
from .queue import QUEUE_DIRNAME, TASKS_DIRNAME
from .errors import EXIT_FINDINGS, EXIT_OK, SkillError
from .index import sort_key
from .record import today
from .report import record_line


class QueueCli(Cli):
    """Очередь как порядок: строка на запись, положение дел в конце."""

    entry = "tqueue"
    area = "очередь как порядок"
    commands = (
        Command("find", "найти очереди проекта: реестр и папки tasks",
                flags=[("--scan", bool, "искать очереди в папках tasks, которых нет в реестре")]),
        Command("init", "создать очередь: индекс с пустым списком",
                flags=[("alias", None, "алиас очереди"),
                       ("--path", None, "путь очереди; по умолчанию tasks/<алиас>")],
                mutating=True),
        Command("list", "список записей с отбором",
                flags=[("--status", None, "отбор по статусу"),
                       ("--type", None, "отбор по типу записи"),
                       ("--release", None, "отбор по релизу"),
                       ("--phase", None, "отбор по фазе"),
                       ("--owner", None, "отбор по владельцу"),
                       ("--overdue", bool, "только записи с горящим сроком"),
                       ("--parked", bool, "только отложенные: статус parked"),
                       ("--order", None, "поле порядка: priority, phase, due, id, updated_at")]),
        Command("next", "следующая работа: что брать в работу",
                flags=[("--count", int, "сколько записей напечатать")]),
        Command("summary", "положение дел очереди по статусам"),
        Command("done", "история: закрытые и отменённые записи",
                flags=[("--release", None, "отбор по релизу")]),
        Command("sort", "порядок очереди: пересчитать и напечатать",
                flags=[("--order", None, "поле порядка: priority, phase, due, id, updated_at"),
                       ("--save", bool, "записать пересчитанный порядок в индекс")],
                mutating=True),
        Command("gantt", "полосы сроков: по одной строке на запись со сроком",
                flags=[("--release", None, "отбор по релизу")]),
        Command("board", "положение дел одним вызовом: работа, следующая, блоки, отложенное, сроки"),
        Command("index-rebuild", "пересборка индекса из папки записей",
                mutating=True),
    )

    #: Поля порядка, которые команда `sort` и `list` умеют.
    ORDER_FIELDS = ("priority", "phase", "due", "id", "updated_at")

    # --- команды ---
    def cmd_find(self, args):
        self.registry = self.registry or _registry(self)
        entries = self.registry.entries()
        lines = ["%s %s %s" % (str(e.get("alias")).ljust(12),
                               str(e.get("path")),
                               str(e.get("updated_at") or "-")) for e in entries]
        found = []
        if getattr(args, "scan", False):
            found = _scan(self.root, {e.get("alias") for e in entries})
            lines.extend("%s %s не в реестре" % (alias.ljust(12), path)
                         for alias, path in found)
        payload = {"queues": entries, "unregistered": [{"alias": a, "path": p}
                                                       for a, p in found]}
        return self.print_lines(lines or ["очередей не найдено"], payload,
                                next_action="tqueue init <алиас>" if not entries
                                else "tqueue list")

    def cmd_init(self, args):
        alias = getattr(args, "alias", None)
        if not alias:
            raise SkillError("ASK_USER", "алиас очереди не назван", "tqueue init",
                             hint="алиас — имя папки очереди",
                             command="tqueue init <алиас>")
        self.registry = _registry(self)
        path = getattr(args, "path", None) or _default_path(self.root, alias)
        self.registry.register(alias, path)
        queue = _queue(self, alias, path)
        index_path = queue.init()
        self.queue = queue
        lines = ["очередь %s создана: %s" % (alias, index_path),
                 "папки записей нет до первой записи: %s" % queue.data_dir]
        return self.print_lines(lines, {"alias": alias, "path": path,
                                        "index": index_path,
                                        "data_dir_created": False},
                                next_action="ttask new <заголовок> --type <тип>")

    def cmd_list(self, args):
        queue = self.resolve_queue(args)
        rows = self._select(queue, args)
        lines = [record_line(row) for row in rows]
        return self.print_lines(lines, {"rows": rows, "count": len(rows)},
                                counts=queue.counts(),
                                next_action=_next_action(queue))

    def cmd_next(self, args):
        queue = self.resolve_queue(args)
        rows = queue.next_candidates()
        count = getattr(args, "count", None) or 1
        rows = rows[:count]
        lines = [record_line(row) for row in rows] or ["в работу брать нечего"]
        return self.print_lines(lines, {"rows": rows}, counts=queue.counts(),
                                next_action="ttask show %s" % rows[0]["id"]
                                if rows else "tqueue list")

    def cmd_summary(self, args):
        queue = self.resolve_queue(args)
        counts = queue.counts()
        lines = ["%s %d" % (label, counts.get(key, 0))
                 for key, label in (("all", "всего"), ("draft", "черновиков"),
                                    ("ready", "готово"), ("in_progress", "в работе"),
                                    ("blocked", "заблокировано"),
                                    ("parked", "отложено"), ("mirror", "зеркал"),
                                    ("closed", "закрыто"),
                                    ("cancelled", "отменено"))]
        return self.print_lines(lines, {"counts": counts}, counts=counts,
                                next_action=_next_action(queue))

    def cmd_done(self, args):
        queue = self.resolve_queue(args)
        rows = [r for r in queue.rows()
                if r.get("status") in ("closed", "cancelled")]
        release = getattr(args, "release", None)
        if release:
            rows = [r for r in rows if r.get("release") == release]
        lines = [record_line(row) for row in rows] or ["закрытых записей нет"]
        return self.print_lines(lines, {"rows": rows}, counts=queue.counts(),
                                next_action="tqueue list")

    def cmd_sort(self, args):
        queue = self.resolve_queue(args)
        rows = self._ordered(queue, getattr(args, "order", None))
        if getattr(args, "save", False):
            queue.index.items = rows
            queue.index.save()
        lines = [record_line(row) for row in rows]
        return self.print_lines(lines, {"rows": rows}, counts=queue.counts(),
                                next_action="tqueue list")

    def cmd_gantt(self, args):
        queue = self.resolve_queue(args)
        rows = [r for r in queue.rows() if isinstance(r.get("due"), str)]
        release = getattr(args, "release", None)
        if release:
            rows = [r for r in rows if r.get("release") == release]
        rows.sort(key=lambda r: (r.get("due") or "", r.get("id") or ""))
        lines = [_bar(row, today()) for row in rows] or ["записей со сроком нет"]
        return self.print_lines(lines, {"rows": rows}, counts=queue.counts(),
                                next_action="tqueue list --overdue")

    def cmd_board(self, args):
        """Положение дел одним вызовом вместо summary, list, next и gantt."""
        queue = self.resolve_queue(args)
        counts = queue.counts()
        work = [r for r in queue.rows() if r.get("status") == "in_progress"]
        blocked = [r for r in queue.rows() if r.get("status") == "blocked"]
        parked = [r for r in queue.rows() if r.get("status") == "parked"]
        overdue = queue.overdue(today())
        following = queue.next_candidates()[:3]
        lines = ["в работе %d" % len(work)]
        lines += ["  " + record_line(r) for r in work]
        lines.append("следующая работа %d" % len(following))
        lines += ["  " + record_line(r) for r in following]
        lines.append("заблокировано %d" % len(blocked))
        lines += ["  " + record_line(r) for r in blocked]
        lines.append("отложено %d" % len(parked))
        lines += ["  " + record_line(r) for r in parked]
        lines.append("сроки горят %d" % len(overdue))
        lines += ["  " + _bar(r, today()) for r in overdue]
        payload = {"counts": counts,
                   "in_progress": [r["id"] for r in work],
                   "next": [r["id"] for r in following],
                   "blocked": [r["id"] for r in blocked],
                   "parked": [r["id"] for r in parked],
                   "overdue": [r["id"] for r in overdue]}
        return self.print_lines(lines, payload, counts=counts,
                                next_action=_next_action(queue))

    def cmd_index_rebuild(self, args):
        queue = self.resolve_queue(args)
        path = queue.rebuild_index()
        rows = queue.rows()
        lines = ["индекс пересобран из папки записей: %s" % path,
                 "строк %d, порядок сохранён" % len(rows)]
        lines += [record_line(row) for row in rows]
        return self.print_lines(lines, {"index": path, "rows": rows},
                                counts=queue.counts(),
                                next_action="tcheck validate --all")

    # --- отбор и порядок ---
    def _select(self, queue, args):
        rows = queue.rows()
        for key, flag in (("status", "status"), ("type", "type"),
                          ("release", "release"), ("phase", "phase"),
                          ("owner", "owner")):
            value = getattr(args, flag, None)
            if value:
                rows = [r for r in rows if str(r.get(key)) == str(value)]
        if getattr(args, "parked", False):
            rows = [r for r in rows if r.get("status") == "parked"]
        if getattr(args, "overdue", False):
            overdue = {r["id"] for r in queue.overdue(today())}
            rows = [r for r in rows if r.get("id") in overdue]
        order = getattr(args, "order", None)
        if order:
            rows = self._ordered(queue, order, rows)
        return rows

    def _ordered(self, queue, order, rows=None):
        rows = list(queue.rows() if rows is None else rows)
        if not order:
            return rows
        if order not in self.ORDER_FIELDS:
            raise SkillError("KEY_UNKNOWN",
                             "поля порядка «%s» нет" % order, "tqueue sort",
                             hint="поле порядка — %s" % ", ".join(self.ORDER_FIELDS),
                             command="tqueue sort --order %s"
                                     % "|".join(self.ORDER_FIELDS))
        mirror_last = sort_key({"status": "mirror"})[0]
        return sorted(rows, key=lambda r: (
            1 if r.get("status") == "mirror" else mirror_last,
            str(r.get(order) or ""), str(r.get("id") or "")))


def _registry(cli):
    from .queue import Registry
    return Registry(cli.root)


def _queue(cli, alias, path=None):
    from .queue import Queue
    return Queue(cli.root, alias, base_dir=path)


def _default_path(root, alias):
    import os
    return os.path.join(root, TASKS_DIRNAME, alias)


def _scan(root, known):
    """Очереди в папках tasks, которых нет в реестре."""
    import os
    found = []
    base = os.path.join(root, TASKS_DIRNAME)
    if not os.path.isdir(base):
        return found
    for name in sorted(os.listdir(base)):
        folder = os.path.join(base, name)
        if name in known or not os.path.isdir(folder):
            continue
        if os.path.isdir(os.path.join(folder, QUEUE_DIRNAME)):
            found.append((name, folder))
    return found


def _bar(row, today_iso):
    """Полоса срока: сколько дней до срока или сколько просрочено."""
    due = row.get("due")
    try:
        delta = (_date(due) - _date(today_iso)).days
    except (TypeError, ValueError):
        delta = None
    if delta is None:
        mark = "срок не разобрать"
    elif delta < 0:
        mark = "просрочено на %d дн." % abs(delta)
    elif delta == 0:
        mark = "срок сегодня"
    else:
        mark = "осталось %d дн." % delta
    width = 0 if delta is None else max(0, min(20, 20 - delta))
    return "%s %s %s %s" % (str(row.get("id")).ljust(6), str(due).ljust(10),
                            "#" * width or "-", mark)


def _date(value):
    import datetime
    return datetime.date.fromisoformat(str(value)[:10])


def _next_action(queue):
    following = queue.next_candidates()
    if following:
        return "ttask show %s" % following[0].get("id")
    if queue.counts().get("draft"):
        return "ttask status <id> --status ready --by <имя>"
    return "ttask new <заголовок> --type <тип>"
