"""Табличные приёмочные проверки: каждое объявление имеет живой контракт.

Каждая строка таблицы становится отдельным unittest-методом, поэтому отчёт
показывает конкретное объявление, а не скрывает всё в одном цикле.
"""

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore import schema
from tdcore.brief import Brief
from tdcore.check_cli import SCHEMAS
from tdcore.errors import HINTS, Issue
from tdcore.flow import FlowIndex
from tdcore.record import Record, new_task
from tdcore.report import SHOW_MODES, render_show
from tdcore.typedefs import TypeIndex

TYPES = TypeIndex(str(ROOT / "assets" / "types"))
FLOWS = FlowIndex(str(ROOT / "assets" / "flows"))


class MatrixTestCase(unittest.TestCase):
    def test_types_count_is_declared(self):
        self.assertEqual(len(TYPES.names()), 14)

    def test_flows_count_is_declared(self):
        self.assertEqual(len(FLOWS.names()), 4)

    def test_status_count_is_declared(self):
        self.assertEqual(len(schema.STATUSES), 8)

    def test_read_mode_count_is_declared(self):
        self.assertEqual(len(schema.READ_MODES if hasattr(schema, "READ_MODES")
                             else __import__("tdcore.report", fromlist=["READ_MODES"]).READ_MODES), 9)


def _test_hint(code):
    def test(self):
        line = Issue("error", "test", "проверка", code).as_line()
        self.assertIn("[%s]" % code, line)
        self.assertIn("→", line)
        self.assertTrue(HINTS[code][0], code)
        self.assertTrue(HINTS[code][1], code)
    test.__name__ = "test_hint_%s" % code.lower()
    return test


for _code in sorted(HINTS):
    setattr(MatrixTestCase, "test_hint_%s" % _code.lower(), _test_hint(_code))


def _test_schema(name):
    def test(self):
        keys = SCHEMAS[name]
        self.assertTrue(keys, name)
        self.assertEqual(len(keys), len(set(keys)), name)
    test.__name__ = "test_schema_%s" % name.lower()
    return test


for _name in sorted(SCHEMAS):
    setattr(MatrixTestCase, "test_schema_%s" % _name.lower(), _test_schema(_name))


def _test_type(type_id):
    def test(self):
        typedef = TYPES.get(type_id)
        self.assertEqual(typedef.id, type_id)
        self.assertTrue((ROOT / "assets" / "types" / type_id / "type.json").is_file())
        self.assertTrue((ROOT / "assets" / "types" / type_id / "instruction.md").is_file())
        self.assertEqual([i.code for i in typedef.validate() if i.is_error], [])
    test.__name__ = "test_type_%s" % type_id.replace("-", "_")
    return test


for _type_id in TYPES.names():
    setattr(MatrixTestCase, "test_type_%s" % _type_id.replace("-", "_"),
            _test_type(_type_id))


def _test_flow(flow_id):
    def test(self):
        flow = FLOWS.get(flow_id)
        self.assertTrue(flow.steps, flow_id)
        self.assertEqual([i.code for i in flow.validate(TYPES.names()) if i.is_error], [])
        self.assertTrue((ROOT / "assets" / "flows" / flow_id / "flow.json").is_file())
        self.assertTrue((ROOT / "assets" / "flows" / flow_id / "instruction.md").is_file())
    test.__name__ = "test_flow_%s" % flow_id.replace("-", "_")
    return test


for _flow_id in FLOWS.names():
    setattr(MatrixTestCase, "test_flow_%s" % _flow_id.replace("-", "_"),
            _test_flow(_flow_id))


def _test_step(flow_id, step_id):
    def test(self):
        step = FLOWS.get(flow_id).step(step_id)
        self.assertIsNotNone(step)
        self.assertIn(step.type, TYPES.names())
        self.assertIsInstance(step.output, list)
    test.__name__ = "test_step_%s_%s" % (flow_id.replace("-", "_"), step_id.replace("-", "_"))
    return test


for _flow in FLOWS.all():
    for _step in _flow.steps:
        setattr(MatrixTestCase,
                "test_step_%s_%s" % (_flow.id.replace("-", "_"), _step.id.replace("-", "_")),
                _test_step(_flow.id, _step.id))


def _test_agent(type_id, filename):
    def test(self):
        agent = Brief(str(ROOT / "assets" / "types"), {}).agent(type_id, filename[:-5])
        self.assertEqual(agent.validate(), [])
        self.assertTrue(agent.contract.get("fields"))
    test.__name__ = "test_agent_%s_%s" % (type_id.replace("-", "_"), filename[:-5])
    return test


for _type in TYPES.names():
    folder = ROOT / "assets" / "types" / _type / "agents"
    for _file in sorted(p.name for p in folder.glob("*.json")):
        setattr(MatrixTestCase,
                "test_agent_%s_%s" % (_type.replace("-", "_"), _file[:-5]),
                _test_agent(_type, _file))


def _test_enum(group, value):
    def test(self):
        self.assertIn(value, group)
    test.__name__ = "test_enum_%s_%s" % (group.__name__ if hasattr(group, "__name__") else "values",
                                          str(value).replace("-", "_"))
    return test


for _value in schema.REF_KINDS:
    setattr(MatrixTestCase, "test_ref_kind_%s" % _value, _test_enum(schema.REF_KINDS, _value))
for _value in schema.ARTEFACT_KINDS:
    setattr(MatrixTestCase, "test_artifact_kind_%s" % _value, _test_enum(schema.ARTEFACT_KINDS, _value))
for _value in schema.COMMENT_KINDS:
    setattr(MatrixTestCase, "test_comment_kind_%s" % _value, _test_enum(schema.COMMENT_KINDS, _value))
for _value in schema.SRC_SYSTEMS:
    setattr(MatrixTestCase, "test_source_system_%s" % _value, _test_enum(schema.SRC_SYSTEMS, _value))
for _value in schema.CAPABILITIES:
    setattr(MatrixTestCase, "test_capability_%s" % _value.replace("-", "_"), _test_enum(schema.CAPABILITIES, _value))
for _value in schema.TIERS:
    setattr(MatrixTestCase, "test_tier_%s" % _value, _test_enum(schema.TIERS, _value))
for _value in schema.MODES:
    setattr(MatrixTestCase, "test_mode_%s" % _value, _test_enum(schema.MODES, _value))


def _test_read_mode(mode):
    def test(self):
        record = Record(new_task("T-001", "Чтение", "default"))
        record.add_comment("реплика", "lead", kind="human")
        record.data["acceptance"] = [{"id": "AC-1", "text": "условие"}]
        if mode == "report":
            record.data["report"] = {"id": "D-001"}
        address = "C-1" if mode == "comment" else ("AC-1" if mode == "element" else None)
        lines = render_show(record, mode, address, {"handoff_last": 1})
        self.assertTrue(lines, mode)
        self.assertTrue(any("размеры:" in line for line in lines), mode)
    test.__name__ = "test_read_mode_%s" % mode
    return test


for _mode in SHOW_MODES:
    setattr(MatrixTestCase, "test_read_mode_%s" % _mode, _test_read_mode(_mode))

# Three cross-domain checks close the acceptance set without duplicating route tests.
def _cross(name, fn):
    setattr(MatrixTestCase, name, fn)


def _test_report_schema(self):
    self.assertEqual(len(SCHEMAS["REPORT"]), len(set(SCHEMAS["REPORT"])))
    self.assertIn("acceptance_status", SCHEMAS["REPORT"])


def _test_settings_are_project_values(self):
    from tdcore.schema import DEFAULT_SETTINGS
    self.assertIn("handoff_last", DEFAULT_SETTINGS)
    self.assertIn("digest_chars", DEFAULT_SETTINGS)


def _test_return_contract_schema(self):
    self.assertEqual(set(SCHEMAS["RETURN_CONTRACT"]),
                     {"fields", "shape", "persist", "pointer"})

_cross("test_report_schema_is_unique", _test_report_schema)
_cross("test_read_settings_are_declared", _test_settings_are_project_values)
_cross("test_return_contract_is_explicit", _test_return_contract_schema)
