"""Unit tests for task-analytics. Run: python3 -m unittest discover -s tests -v"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "task-analytics.py"
T0 = 1_790_000_000_000


def make_db(path, sessions):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE project (id TEXT, worktree TEXT);
        CREATE TABLE project_directory (project_id TEXT, directory TEXT);
        CREATE TABLE session (
            id TEXT PRIMARY KEY, project_id TEXT, parent_id TEXT, title TEXT,
            directory TEXT, cost REAL, tokens_input INTEGER, tokens_output INTEGER,
            tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER,
            model TEXT, agent TEXT, time_created INTEGER, time_updated INTEGER
        );
        CREATE TABLE message (
            id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT
        );
        CREATE TABLE part (
            id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT,
            time_created INTEGER, time_updated INTEGER, data TEXT
        );
        """
    )
    for session in sessions:
        connection.execute(
            "INSERT INTO session VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session["id"], session["project_id"], session.get("parent_id"), session.get("title", ""),
                session["directory"], session.get("cost", 0), session.get("tokens_input", 0),
                session.get("tokens_output", 0), session.get("tokens_reasoning", 0),
                session.get("tokens_cache_read", 0), session.get("tokens_cache_write", 0),
                session.get("model", "test-model"), session.get("agent", "build"),
                session["time_created"], session["time_updated"],
            ),
        )
        for message in session.get("messages", []):
            connection.execute(
                "INSERT INTO message VALUES (?,?,?,?)",
                (message["id"], session["id"], message["t"], json.dumps(message["data"])),
            )
        for part in session.get("parts", []):
            connection.execute(
                "INSERT INTO part VALUES (?,?,?,?,?,?)",
                (part["id"], part["message_id"], session["id"], part["t"], part["t"], json.dumps(part["data"])),
            )
    connection.execute("INSERT INTO project VALUES (?,?)", ("p1", sessions[0]["directory"]))
    connection.execute("INSERT INTO project_directory VALUES (?,?)", ("p1", sessions[0]["directory"]))
    connection.commit()
    connection.close()


def base_session(session_id="ses_test0001", directory="/tmp/project", last=None):
    last = last or T0 + 60_000
    return {
        "id": session_id,
        "project_id": "p1",
        "directory": directory,
        "time_created": T0,
        "time_updated": last,
        "cost": 0.5,
        "tokens_input": 100,
        "tokens_output": 20,
        "tokens_reasoning": 10,
        "messages": [
            {"id": "msg_u", "t": T0 + 1000, "data": {"role": "user"}},
            {"id": "msg_a", "t": T0 + 2000, "data": {
                "role": "assistant", "modelID": "test-model", "cost": 0.5,
                "tokens": {"input": 100, "output": 20, "reasoning": 10,
                           "cache": {"read": 40, "write": 5}},
            }},
        ],
        "parts": [
            {"id": "prt_u", "message_id": "msg_u", "t": T0 + 1000,
             "data": {"type": "text", "text": "prepare plan for task 2628 secret token=abc123"}},
            {"id": "prt_t", "message_id": "msg_a", "t": T0 + 2000,
             "data": {"type": "tool", "tool": "bash", "callID": "c1", "state": {
                 "status": "completed", "input": {"command": "php -l lib/Foo.php?token=abc123"},
                 "output": "ok", "time": {"start": T0 + 2000, "end": T0 + 2500},
             }}},
        ],
    }


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        self.tasks = self.root / ".doc" / "tasks"
        self.tasks.mkdir(parents=True)
        self.out = Path(self.tmp.name) / "out"
        self.db_path = Path(self.tmp.name) / "fixture.db"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        command = [sys.executable, str(CLI), "--db", str(self.db_path), "--root", str(self.root),
                   "--tasks-root", str(self.tasks), "--out", str(self.out), *args]
        return subprocess.run(command, capture_output=True, text=True)

    def test_scan_writes_and_redacts(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        result = self.run_cli("scan", "--allow-partial")
        self.assertEqual(result.returncode, 0, result.stderr)
        files = list((self.out / "unassigned").glob("ses_*.json"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertNotIn("abc123", text)
        payload = json.loads(text)
        self.assertEqual(payload["token_ledger"]["cache_read"], 40)
        self.assertEqual(payload["token_ledger"]["input_fresh"], 100)
        self.assertEqual(payload["token_ledger"]["incoming_total"], 145)
        self.assertEqual(payload["token_ledger"]["requests"], 1)

    def test_partial_session_exit_code(self):
        session = base_session(directory=str(self.root), last=int(time.time() * 1000) - 60_000)
        session["parts"][1]["data"]["state"]["status"] = "running"
        session["parts"][1]["data"]["state"].pop("output", None)
        make_db(self.db_path, [session])
        result = self.run_cli("scan")
        self.assertEqual(result.returncode, 1)
        allowed = self.run_cli("scan", "--allow-partial")
        self.assertEqual(allowed.returncode, 0)
        payload = json.loads(next((self.out / "unassigned").glob("ses_*.json")).read_text(encoding="utf-8"))
        self.assertFalse(payload["final"])
        codes = [finding["code"] for finding in payload["findings"]]
        self.assertIn("unpaired", codes)

    def test_anchor_attribution(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        anchor = self.run_cli("anchor", "--task", "2628", "--branch", "bugfixes/#2628",
                              "--quote", "prepare plan for task 2628")
        self.assertEqual(anchor.returncode, 0, anchor.stderr)
        result = self.run_cli("scan", "--allow-partial")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.tasks / "2628" / "dialogs" / "ses_test0001.json"
        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task"], "2628")
        self.assertEqual(payload["confidence"], 1.0)

    def test_unassigned_without_anchor(self):
        session = base_session(directory=str(self.root))
        session["parts"][1]["data"]["state"]["input"]["command"] = "cat .doc/tasks/2628/notes.md"
        make_db(self.db_path, [session])
        result = self.run_cli("scan", "--allow-partial")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(list((self.out / "unassigned").glob("ses_*.json")))
        self.assertFalse((self.tasks / "2628").exists())

    def test_deterministic_rerun(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        self.run_cli("scan", "--allow-partial")
        first = next((self.out / "unassigned").glob("ses_*.json")).read_bytes()
        self.run_cli("scan", "--allow-partial")
        second = next((self.out / "unassigned").glob("ses_*.json")).read_bytes()
        self.assertEqual(first, second)


    def test_first_message_attribution(self):
        session = base_session(directory=str(self.root))
        session["parts"][0]["data"]["text"] = "перейди к задаче 2628 и посмотри оплату"
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        files = list((self.tasks / "2628" / "dialogs").glob("ses_*.json")) + list((self.out / "unassigned").glob("ses_*.json"))
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["task"], "2628")
        self.assertEqual(payload["confidence"], 0.85)
        signals = [item["signal"] for item in payload["attribution"]]
        self.assertIn("first_message_directive", signals)

    def test_mcp_servers_and_batch_savings(self):
        session = base_session(directory=str(self.root))
        parts = []
        for index, name in enumerate(("a.php", "b.php", "c.php")):
            parts.append({
                "id": f"prt_r{index}", "message_id": "msg_a", "t": T0 + 3000 + index * 1000,
                "data": {"type": "tool", "tool": "read", "callID": f"c{index}", "state": {
                    "status": "completed",
                    "input": {"filePath": f"/tmp/project/{name}"},
                    "output": "x",
                    "time": {"start": T0 + 3000 + index * 1000, "end": T0 + 4000 + index * 1000},
                }},
            })
        parts.append({
            "id": "prt_exec", "message_id": "msg_a", "t": T0 + 7000,
            "data": {"type": "tool", "tool": "execute", "callID": "cexec", "state": {
                "status": "completed", "input": {"code": "return 1"},
                "output": "1", "time": {"start": T0 + 7000, "end": T0 + 7100},
                "metadata": {"toolCalls": [
                    {"tool": "serena.find_symbol", "status": "completed"},
                    {"tool": "graphify.query_graph", "status": "error"},
                ]},
            }},
        })
        session["parts"] = parts
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        path = next((self.out / "unassigned").glob("ses_*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        servers = {item["server"]: item for item in payload["mcp_servers"]}
        self.assertEqual(servers["serena"]["calls"], 1)
        self.assertEqual(servers["graphify"]["errors"], 1)
        self.assertEqual(payload["batchable_saved_calls"], 2)
        self.assertGreaterEqual(payload["batchable_saved_ms"], 0)

    def test_active_time_caps_idle_gaps(self):
        session = base_session(directory=str(self.root))
        first = session["parts"][1]
        first["t"] = T0 + 1000
        second = dict(first)
        second["id"] = "prt_t2"
        second["t"] = T0 + 1000 + 5 * 60 * 1000
        third = dict(first)
        third["id"] = "prt_t3"
        third["t"] = T0 + 1000 + 65 * 60 * 1000
        session["parts"] = [first, second, third]
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        path = next((self.out / "unassigned").glob("ses_*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["duration_ms"], 65 * 60 * 1000)
        self.assertEqual(payload["active_ms"], 5 * 60 * 1000 + 15 * 60 * 1000)
        self.assertEqual(payload["idle_trimmed_ms"], 5 * 60 * 1000 + 15 * 60 * 1000)

    def test_backfill_anchors(self):
        session = base_session(directory=str(self.root))
        for index in range(5):
            part = dict(session["parts"][1])
            part["id"] = f"prt_p{index}"
            part["data"] = json.loads(json.dumps(part["data"]))
            part["data"]["state"]["input"]["command"] = f"cat .doc/tasks/2628/file{index}.md"
            session["parts"].append(part)
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        result = self.run_cli("backfill-anchors")
        self.assertEqual(result.returncode, 0, result.stderr)
        anchor = self.tasks / "2628" / "_dialogs" / "anchor.json"
        self.assertTrue(anchor.exists())
        payload = json.loads(anchor.read_text(encoding="utf-8"))
        self.assertEqual(payload["task"], "2628")
        self.assertNotIn("abc123", payload["quote"])


    def test_bare_hash_is_not_enough(self):
        session = base_session(directory=str(self.root))
        session["parts"][0]["data"]["text"] = "посмотри #2628 и оплату"
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        path = next((self.out / "unassigned").glob("ses_*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNone(payload["task"])
        self.assertEqual(payload["attribution_status"], "unassigned")

    def test_ambiguous_two_tasks(self):
        session = base_session(directory=str(self.root))
        session["parts"][0]["data"]["text"] = "задача 2628 и задача 2618, сравни оплату"
        make_db(self.db_path, [session])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        path = next((self.out / "unassigned").glob("ses_*.json"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNone(payload["task"])
        self.assertEqual(payload["attribution_status"], "ambiguous")
        self.assertEqual(len(payload["task_candidates"]), 2)

    def test_manual_assign_writes_anchor(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        result = self.run_cli("assign", "--session", "ses_test0001", "--task", "2628")
        self.assertEqual(result.returncode, 0, result.stderr)
        anchor = self.tasks / "2628" / "_dialogs" / "anchor.json"
        self.assertTrue(anchor.exists())
        payload = json.loads(anchor.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"], "manual-assign")

    def test_detach_moves_session_to_unassigned(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        anchor = self.run_cli("anchor", "--task", "2628", "--branch", "x",
                              "--quote", "prepare plan for task 2628")
        self.assertEqual(anchor.returncode, 0, anchor.stderr)
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        assigned = self.tasks / "2628" / "dialogs" / "ses_test0001.json"
        self.assertTrue(assigned.exists())
        result = self.run_cli("detach", "--session", "ses_test0001", "--task", "2628", "--reason", "test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(assigned.exists())
        moved = self.out / "unassigned" / "ses_test0001.json"
        self.assertTrue(moved.exists())
        payload = json.loads(moved.read_text(encoding="utf-8"))
        self.assertIsNone(payload["task"])
        self.assertEqual(payload["attribution_status"], "detached")
        self.assertEqual(payload["detached_from"], "2628")
        index = json.loads((self.tasks / "2628" / "dialogs" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["sessions"], [])
        self.assertEqual(self.run_cli("scan", "--allow-partial").returncode, 0)
        payload = json.loads(moved.read_text(encoding="utf-8"))
        self.assertIsNone(payload["task"])

    def test_validate_detects_broken_link(self):
        make_db(self.db_path, [base_session(directory=str(self.root))])
        self.run_cli("anchor", "--task", "2628", "--branch", "x", "--quote", "prepare plan for task 2628")
        self.run_cli("scan", "--allow-partial")
        analysis = self.tasks / "2628" / "dialogs" / "ses_test0001.json"
        analysis.unlink()
        result = self.run_cli("validate")
        self.assertEqual(result.returncode, 2)
        self.assertIn("broken link", result.stdout)


if __name__ == "__main__":
    unittest.main()
