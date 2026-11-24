"""Проверки трёх CLI: разбор маршрутов и основные вертикальные действия."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore.check_cli import CheckCli
from tdcore.cli import EXIT_FINDINGS, EXIT_OK
from tdcore.queue import Queue, Registry
from tdcore.queue_cli import QueueCli
from tdcore.task_cli import TaskCli


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        Registry(str(self.root)).register("site", str(self.root / "tasks" / "site"))
        Queue(str(self.root), "site").init()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, cls, argv):
        out, err = io.StringIO(), io.StringIO()
        code = cls(root=str(self.root), out=out, err=err).main(argv)
        return code, out.getvalue(), err.getvalue()

    def create(self, kind="default", title="Запись"):
        code, out, err = self.call(TaskCli, ["new", title, "--type", kind])
        self.assertEqual(code, EXIT_OK, err)
        return "T-001"

    def test_tqueue_list_has_state(self):
        code, out, err = self.call(QueueCli, ["list", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("состояние:", out)

    def test_tqueue_summary_empty(self):
        code, out, err = self.call(QueueCli, ["summary", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("всего 0", out)

    def test_tqueue_board_empty(self):
        code, out, err = self.call(QueueCli, ["board", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("заблокировано 0", out)

    def test_tqueue_next_empty(self):
        code, out, err = self.call(QueueCli, ["next", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("брать нечего", out)

    def test_tqueue_done_empty(self):
        code, out, err = self.call(QueueCli, ["done", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("закрытых записей нет", out)

    def test_tqueue_gantt_empty(self):
        code, out, err = self.call(QueueCli, ["gantt", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("сроком нет", out)

    def test_tqueue_sort_empty(self):
        code, out, err = self.call(QueueCli, ["sort", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("состояние:", out)

    def test_tqueue_index_rebuild_empty(self):
        code, out, err = self.call(QueueCli, ["index-rebuild", "--queue", "site"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("индекс пересобран", out)

    def test_new_and_json(self):
        code, out, err = self.call(TaskCli, ["new", "Запись", "--type", "default", "--json"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertEqual(json.loads(out)["id"], "T-001")

    def test_set_two_fields(self):
        self.create()
        code, out, err = self.call(TaskCli, ["set", "T-001", "--phase", "core",
                                             "--priority", "1", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("p1", out)

    def test_set_multiple_ids_from_option(self):
        self.create()
        q = Queue(str(self.root), "site")
        q.create("Вторая", "default")
        code, out, err = self.call(TaskCli, ["set", "--ids", "T-001,T-002",
                                             "--phase", "core", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("T-001", out)
        self.assertIn("T-002", out)

    def test_set_acceptance_elements(self):
        self.create("default")
        code, out, err = self.call(TaskCli, ["set", "T-001", "--acceptance", "файл",
                                             "--acceptance", "тест", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        code, out, err = self.call(TaskCli, ["show", "T-001/AC-2"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("тест", out)

    def test_status_ready(self):
        self.create()
        code, out, err = self.call(TaskCli, ["status", "T-001", "--status", "ready",
                                             "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("ready", out)

    def test_claim_and_unclaim(self):
        self.create()
        code, out, err = self.call(TaskCli, ["claim", "T-001", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        code, out, err = self.call(TaskCli, ["unclaim", "T-001", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)

    def test_comment_modes(self):
        self.create()
        code, out, err = self.call(TaskCli, ["comment", "add", "T-001", "--body", "реплика",
                                             "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        code, out, err = self.call(TaskCli, ["comment", "list", "T-001"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("C-1", out)
        code, out, err = self.call(TaskCli, ["comment", "brief", "T-001"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("реплика", out)

    def test_ref_add_and_tree(self):
        self.create()
        code, out, err = self.call(TaskCli, ["ref", "add", "T-001", "--kind", "file",
                                             "--path", "a.py", "--note", "точка", "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        code, out, err = self.call(TaskCli, ["tree", "T-001"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("refs", out)

    def test_digest_part(self):
        self.create()
        code, out, err = self.call(TaskCli, ["digest", "T-001"])
        self.assertEqual(code, EXIT_OK, err)
        code, out, err = self.call(TaskCli, ["digest", "T-001", "--part", "body"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Тело записи", out)

    def test_immutable_type_error(self):
        self.create()
        code, out, err = self.call(TaskCli, ["set", "T-001", "--type", "fix", "--by", "lead"])
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("TYPE_IMMUTABLE", err)

    def test_unknown_read_mode_error(self):
        self.create()
        code, out, err = self.call(TaskCli, ["show", "T-001", "--mode", "unknown"])
        self.assertEqual(code, EXIT_FINDINGS)
        self.assertIn("READ_MODE_UNKNOWN", err)

    def test_check_schema_json(self):
        code, out, err = self.call(CheckCli, ["schema", "TASK", "--json"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("id", json.loads(out)["TASK"])

    def test_check_types_list(self):
        code, out, err = self.call(CheckCli, ["types", "list"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("planning", out)

    def test_check_types_fields(self):
        code, out, err = self.call(CheckCli, ["types", "fields", "fix"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("reproduce", out)

    def test_check_flows_list(self):
        code, out, err = self.call(CheckCli, ["flows", "list"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("jira-fix", out)

    def test_check_flows_show(self):
        code, out, err = self.call(CheckCli, ["flows", "show", "jira-fix"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("intake", out)

    def test_check_selftest(self):
        code, out, err = self.call(CheckCli, ["selftest"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("находок 0", out)

    def test_check_doctor_clean_fixture(self):
        fixture = Path(__file__).resolve().parents[1] / "assets" / "examples" / "v6-project"
        code, out, err = self.call(CheckCli, ["doctor", "--root", str(fixture), "--all", "--strict"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("находок 0", out)

    def test_roles_list(self):
        fixture = Path(__file__).resolve().parents[1] / "assets" / "examples" / "v6-project"
        code, out, err = self.call(CheckCli, ["roles", "list", "--root", str(fixture)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("developer", out)

    def test_tools_list_fixture(self):
        fixture = Path(__file__).resolve().parents[1] / "assets" / "examples" / "v6-project"
        code, out, err = self.call(CheckCli, ["tools", "list", "--root", str(fixture)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("code-graph", out)

    def test_import_route(self):
        source = self.root / "jira.json"
        source.write_text(json.dumps({"id": "P-7", "fields": {"summary": "Импорт"}},
                                     ensure_ascii=False), encoding="utf-8")
        code, out, err = self.call(CheckCli, ["import", "jira", "--file", str(source), "--by", "lead"])
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("mirror", out)


# Each declared route gets a separate test: a missing handler or nested action is
# a route regression, not an incidental parser detail.
def _route_test(name, cls, command, action=None):
    def test(self):
        cli = cls(root=str(self.root))
        handler_name = "cmd_%s" % command.replace("-", "_") if action is None \
            else "_%s_%s" % (command.replace("-", "_"), action)
        self.assertTrue(callable(getattr(cli, handler_name, None)), handler_name)
        if action is not None:
            self.assertIsInstance(cli.nested_flags(command, action), list)
    test.__name__ = name
    return test


for _cls in (QueueCli, TaskCli, CheckCli):
    for _command in _cls.commands:
        setattr(CliTestCase,
                "test_route_%s_%s" % (_cls.entry, _command.name.replace("-", "_")),
                _route_test("test_route", _cls, _command.name))
        for _action in _command.nested:
            setattr(CliTestCase,
                    "test_route_%s_%s_%s" % (_cls.entry,
                                             _command.name.replace("-", "_"), _action),
                    _route_test("test_route", _cls, _command.name, _action))


if __name__ == "__main__":
    unittest.main()
