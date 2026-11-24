"""Общий контракт CLI: разбор аргументов, печать, коды возврата, отказ одной строкой.

Три точки входа тонкие: в них только состав команд. Разбор аргументов, печать и
обработка отказа живут здесь — один дом на все три.

Контракт вывода:
1. по умолчанию одна строка на объект, поля в фиксированном порядке;
2. каждый вывод заканчивается положением дел и следующим действием;
3. добровольные срезы --json, --fields, --quiet, --limit;
4. ошибка — одна строка из четырёх частей: код, что не так, чем лечить, команда;
5. команда не печатает ничего, что не относится к запросу;
6. числа в выводе — факты.
"""

import argparse
import os
import sys

from . import schema
from .errors import EXIT_ASK_USER, EXIT_FINDINGS, EXIT_OK, SkillError
from .queue import Queue, Registry
from .report import emit, state_line


#: Общие флаги любой точки входа: наследуются каждой командой.
COMMON_FLAGS = ("--root", "--queue", "--json", "--fields", "--quiet", "--limit",
                "--by")


class Command:
    """Команда точки входа: имя, назначение, флаги и вложенные команды.

    Справка печатает состав команды и каждый её флаг: флаг, которого в справке
    нет, в процедурах не упоминается.
    """

    def __init__(self, name, summary, flags=None, nested=None, mutating=False):
        self.name = name
        self.summary = summary
        self.flags = list(flags or [])
        self.nested = list(nested or [])
        self.mutating = mutating

    def flag_names(self):
        """Имена флагов команды: справка называет каждый используемый флаг."""
        names = []
        for flag in self.flags:
            names.append(flag[0] if isinstance(flag, tuple) else str(flag))
        return names

    def as_line(self):
        """Строка справки: имя, назначение, вложенные команды и все флаги."""
        parts = ["  " + self.name.ljust(16) + self.summary]
        if self.nested:
            parts.append("      вложенные: " + ", ".join(self.nested))
        names = self.flag_names()
        if names:
            parts.append("      флаги: " + ", ".join(names))
        parts.append("      общие флаги: " + ", ".join(COMMON_FLAGS))
        return "\n".join(parts)


class Cli:
    """База точки входа: состав команд, общий разбор, общая печать."""

    entry = "tqueue"
    area = "очередь как порядок"
    commands = ()

    def __init__(self, root=None, out=None, err=None):
        self.root = os.path.abspath(root or os.environ.get("TODONE_ROOT") or os.getcwd())
        self.out = out if out is not None else sys.stdout
        self.err = err if err is not None else sys.stderr
        self.args = None
        self.queue = None
        self.registry = None

    # --- сборка парсера ---
    def common_parser(self):
        """Общие флаги: наследуются каждой командой, идут после имени команды."""
        common = argparse.ArgumentParser(add_help=False)
        common.add_argument("--root", default=None,
                            help="корень проекта: где искать .todone и tasks")
        common.add_argument("--queue", default=None,
                            help="алиас очереди; без него — очередь по умолчанию")
        common.add_argument("--json", action="store_true",
                            help="вывод одним объектом JSON без постороннего текста")
        common.add_argument("--fields", default=None,
                            help="только названные поля строки, через запятую")
        common.add_argument("--quiet", action="store_true", help="только ошибки")
        common.add_argument("--limit", type=int, default=None,
                            help="сколько строк списка печатать")
        common.add_argument("--by", default=None,
                            help="кто правит: имя человека или роль")
        return common

    def build_parser(self):
        self.common = self.common_parser()
        parser = argparse.ArgumentParser(
            prog=self.entry, add_help=True,
            description="%s — %s. Флаги идут после имени команды. Состав команд: %s."
                        % (self.entry, self.area,
                           ", ".join(c.name for c in self.commands)))
        subs = parser.add_subparsers(dest="command")
        for command in self.commands:
            sub = subs.add_parser(command.name, help=command.summary,
                                  description=command.summary,
                                  parents=[self.common])
            self.declare(sub, command)
        return parser

    def declare(self, sub, command):
        """Флаги команды: потомок объявляет свои, база добавляет вложенные."""
        for flag in command.flags:
            self._add_flag(sub, flag)
        if command.nested:
            nested = sub.add_subparsers(dest="action")
            for name in command.nested:
                child = nested.add_parser(name,
                                          help="%s %s" % (command.name, name),
                                          parents=[self.common])
                for flag in self.nested_flags(command.name, name):
                    self._add_flag(child, flag)

    def nested_flags(self, command, action):
        """Флаги вложенной команды: объявляются потомком точки входа."""
        return []

    def _add_flag(self, parser, flag):
        """Добавить флаг по объявлению: имя, тип, помощь.

        Общий флаг команда не переобъявляет: он уже наследуется.
        """
        name = flag[0] if isinstance(flag, tuple) else str(flag)
        if name in COMMON_FLAGS:
            return
        if isinstance(flag, tuple):
            name, kind, help_text = (list(flag) + [None, None, None])[:3]
        else:
            name, kind, help_text = flag, None, None
        kwargs = {"help": help_text or ""}
        if kind is bool:
            kwargs["action"] = "store_true"
        elif kind is int:
            kwargs["type"] = int
        elif kind is not None:
            kwargs["type"] = kind
        if not name.startswith("-") and name == "ids":
            kwargs["nargs"] = "*"
        if not name.startswith("-") and name == "name" \
                and parser.prog.endswith("tcheck schema"):
            kwargs["nargs"] = "?"
        if name == "--ids":
            kwargs["dest"] = "ids_option"
        if name == "--command":
            kwargs["dest"] = "tool_command"
        if name == "--extra" or name in {
                "--goals", "--acceptance", "--in-scope", "--out-of-scope",
                "--context", "--files-hint", "--steps", "--verify",
                "--open-questions", "--notes", "--doc-key", "--changed-file",
                "--task-ref", "--carry-ref", "--include", "--exclude"}:
            kwargs["action"] = "append"
        parser.add_argument(name, **kwargs)

    # --- запуск ---
    def normalize_argv(self, argv):
        """Hook for transport-compatible aliases before argparse."""
        return list(argv)

    def main(self, argv=None):
        argv = list(sys.argv[1:] if argv is None else argv)
        argv = self.normalize_argv(argv)
        parser = self.build_parser()
        if not argv or argv[0] in ("-h", "--help"):
            self.print_composition()
            return EXIT_OK
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            code = exc.code
            return EXIT_OK if code in (0, None) else EXIT_FINDINGS
        self.args = args
        if getattr(args, "root", None):
            self.root = os.path.abspath(args.root)
        if not args.command:
            self.print_composition()
            return EXIT_OK
        try:
            return self.dispatch(args) or EXIT_OK
        except SkillError as exc:
            if getattr(self.args, "json", False) and getattr(exc, "details", None):
                payload = {"error": {"code": exc.code, "message": exc.message,
                                      "where": exc.where, "hint": exc.hint,
                                      "command": exc.command},
                           "details": exc.details}
                self.out.write(_dumps(payload) + "\n")
            else:
                self.err.write(exc.as_line() + "\n")
            return exc.exit_code
        except BrokenPipeError:
            return EXIT_OK

    def dispatch(self, args):
        handler = getattr(self, "cmd_%s" % args.command.replace("-", "_"), None)
        if handler is None:
            raise SkillError("NOT_IMPLEMENTED",
                             "команда «%s» точки входа %s не реализована"
                             % (args.command, self.entry), self.entry,
                             command="%s help" % self.entry)
        return handler(args)

    # --- очередь ---
    def resolve_queue(self, args, required=True):
        """Разрешить очередь: алиас из флага, иначе запись по умолчанию."""
        self.registry = Registry(self.root)
        alias = getattr(args, "queue", None) or self.registry.default_alias()
        if not alias:
            if not required:
                return None
            known = self.registry.entries()
            raise SkillError(
                "QUEUE_NOT_RESOLVED",
                "очередь не названа: в реестре %d %s"
                % (len(known), _plural_queue(len(known))),
                self.registry.path,
                hint="назвать очередь флагом --queue" if known
                     else "создать очередь",
                command="tqueue list --queue <алиас>" if known
                        else "tqueue init <алиас>")
        entry = self.registry.find(alias)
        self.queue = Queue(self.root, alias,
                           base_dir=(entry or {}).get("path"))
        return self.queue

    # --- печать ---
    def print_lines(self, lines, json_obj=None, next_action=None, counts=None):
        """Вывод команды: строки, положение дел и следующее действие."""
        if getattr(self.args, "json", False):
            payload = json_obj if json_obj is not None else {"lines": list(lines)}
            if counts is not None:
                payload = dict(payload) if isinstance(payload, dict) else {"lines": lines}
                payload["counts"] = counts
            if next_action:
                payload["next"] = next_action
            self.out.write(_dumps(payload) + "\n")
            return EXIT_OK
        lines = list(lines)
        if counts is None:
            counts = {"all": len(lines)}
        lines = lines + [state_line(counts, next_action)]
        emit(lines, self.out, fields=_fields(self.args),
             quiet=getattr(self.args, "quiet", False),
             limit=getattr(self.args, "limit", None))
        return EXIT_OK

    def print_composition(self):
        """Состав своих команд: чужие точки входа не печатаются."""
        lines = ["%s — %s" % (self.entry, self.area), ""]
        lines.append("Общие флаги каждой команды: " + ", ".join(COMMON_FLAGS))
        lines.append("")
        lines.append("Команды:")
        for command in self.commands:
            lines.append(command.as_line())
        lines.append("")
        lines.append("команд %d | next: %s <команда> -h"
                     % (len(self.commands), self.entry))
        self.out.write("\n".join(lines) + "\n")
        return EXIT_OK

    def counts(self):
        return self.queue.counts() if self.queue is not None else {"all": 0}

    # --- идентификаторы вызова ---
    def ids_of(self, args, positional="ids"):
        """Идентификаторы вызова: из аргументов, из отбора или из stdin (`--ids -`)."""
        value = getattr(args, positional, None)
        if isinstance(value, (list, tuple)):
            ids = list(value)
        elif value:
            ids = [value]
        else:
            ids = []
        raw = getattr(args, "ids_option", None)
        if isinstance(raw, (list, tuple)):
            raw = ",".join(str(item) for item in raw)
        if raw == "-":
            ids.extend(x.strip() for x in sys.stdin.read().split() if x.strip())
        elif raw:
            ids.extend(x.strip() for x in str(raw).split(",") if x.strip())
        return [i for i in ids if i]

    def require_by(self, args, what):
        """Правка знает, кто её сделал: без --by команда отказывает."""
        who = getattr(args, "by", None)
        if not who:
            raise SkillError("ASK_USER",
                             "%s без имени того, кто правит, не выполняется" % what,
                             "флаг --by",
                             hint="назвать человека или роль",
                             command="… --by <имя>")
        return who

    def paths(self):
        """Пути поставки: типы, потоки, шаблоны — относительно корня скилла."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        skill = os.path.dirname(here)
        return {"skill": skill,
                "types": os.path.join(skill, "assets", "types"),
                "flows": os.path.join(skill, "assets", "flows"),
                "project_types": os.path.join(self.root, ".todone", "types"),
                "project_flows": os.path.join(self.root, ".todone", "flows"),
                "templates": os.path.join(skill, "assets", "templates"),
                "scripts": here}


def _plural_queue(count):
    tail = abs(int(count)) % 100
    if 11 <= tail <= 14:
        return "очередей"
    digit = tail % 10
    if digit == 1:
        return "очередь"
    return "очереди" if 2 <= digit <= 4 else "очередей"


def _dumps(payload):
    import json
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _fields(args):
    raw = getattr(args, "fields", None)
    return [f.strip() for f in raw.split(",")] if raw else None


def run(cli_class, argv=None, root=None):
    """Точка входа: создать CLI, выполнить, вернуть код возврата."""
    cli = cli_class(root=root)
    return cli.main(argv)


def main(cli_class, argv=None):
    """Обёртка точки входа: код возврата в `sys.exit`."""
    sys.exit(run(cli_class, argv))
