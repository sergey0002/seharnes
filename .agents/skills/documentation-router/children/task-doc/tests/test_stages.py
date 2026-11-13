"""J06 stage tests: selection, ambiguity, placeholders, scope resolution,
legacy folder inventory. Documents are published through store.Store.apply
so every fixture also exercises the contract stage rules."""

import unittest
from pathlib import Path

import support
from jsondoc import stages, store


def stage(number, status="planned", placeholder=False, depends_on=(),
          superseded_by=None, plan_artifact_id=None, diff_artifact_ids=(),
          diff_manifest_id=None, test_run_ids=()):
    return {
        "id": f"stage:{number}",
        "number": number,
        "title": f"Стадия {number}",
        "status": status,
        "placeholder": placeholder,
        "trigger": None,
        "depends_on": list(depends_on),
        "superseded_by": superseded_by,
        "plan_artifact_id": plan_artifact_id,
        "diff_artifact_ids": list(diff_artifact_ids),
        "diff_manifest_id": diff_manifest_id,
        "test_artifact_ids": [],
        "test_run_ids": list(test_run_ids),
        "documentation_refs": [],
        "requirement_ids": [],
        "source_ids": [],
    }


def artifact(aid, role, scope, path=None):
    return {
        "id": aid,
        "role": role,
        "path": path or f".doc/tasks/0/artifacts/{aid}.md",
        "sha256": "0" * 64,
        "scope": scope,
        "revision": None,
        "availability": "present",
        "projection_path": None,
        "source_ids": [],
    }


def publish(task_id, doc):
    root, docs = support.make_docs()
    st = store.Store(root, Path(".doc"))
    res = st.apply("task", task_id, {
        "schema_version": "1.0",
        "operation_id": f"op-create-{task_id}",
        "expected_revision": 0,
        "actor": "task-doc",
        "reason": "fixture create",
        "operations": [],
        "document": doc,
    })
    if res["status"] != "applied":
        raise AssertionError(f"fixture publish failed: {res}")
    return docs, st.load("task", task_id)


class StagesViewTests(unittest.TestCase):
    def test_st01_multiple_active_requires_explicit_stage(self):
        doc = support.minimal_task("2701")
        doc["stages"] = [
            stage(1, status="active"),
            stage(2, status="active"),
            stage(3, status="planned"),
        ]
        _, doc = publish("2701", doc)
        view = stages.stages_view(doc)
        self.assertIsNone(view["active_stage_id"])
        self.assertIn("STAGE_AMBIGUOUS", view["warnings"])
        self.assertEqual(view["ambiguous_active_ids"], ["stage:1", "stage:2"])
        self.assertTrue(view["requires_explicit_stage"])
        self.assertEqual(view["next_actionable_stage_ids"], ["stage:3"])

    def test_st01_single_active_resolves_without_warning(self):
        doc = support.minimal_task("2702")
        doc["stages"] = [
            stage(1, status="closed"),
            stage(2, status="active"),
        ]
        _, doc = publish("2702", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["active_stage_id"], "stage:2")
        self.assertEqual(view["warnings"], [])
        self.assertFalse(view["requires_explicit_stage"])
        self.assertEqual(view["ambiguous_active_ids"], [])

    def test_st02_placeholder_occupies_number_with_resume_note(self):
        doc = support.minimal_task("2703")
        doc["artifacts"] = [artifact("art-p1", "plan", "stage:1")]
        doc["stages"] = [
            stage(1, status="closed", plan_artifact_id="art-p1"),
            stage(6, status="unknown", placeholder=True),
        ]
        _, doc = publish("2703", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["next_allocatable_number"], 7)
        notes = [n for n in view["notes"]
                 if n["code"] == "placeholder_reserved"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["stage_id"], "stage:6")
        self.assertEqual(notes[0]["number"], 6)
        self.assertIn("resume stage 6", notes[0]["detail"])
        placeholder_ids = [c["id"] for c in view["active_candidates"]]
        self.assertNotIn("stage:6", placeholder_ids)

    def test_st03_missing_root_plan_does_not_block_stage2(self):
        doc = support.minimal_task("2704")
        doc["artifacts"] = [artifact("art-p2", "plan", "stage:2")]
        doc["stages"] = [
            stage(1, status="planned"),
            stage(2, status="planned", plan_artifact_id="art-p2"),
        ]
        _, doc = publish("2704", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["latest_documented_stage_id"], "stage:2")
        card_one = next(c for c in view["stages"] if c["id"] == "stage:1")
        self.assertEqual(card_one["status"], "planned")
        self.assertIsNone(card_one["plan_artifact_id"])
        self.assertEqual(view["next_actionable_stage_ids"],
                         ["stage:1", "stage:2"])

    def test_st04_depends_on_blocked_is_not_actionable(self):
        doc = support.minimal_task("2705")
        doc["stages"] = [
            stage(1, status="blocked"),
            stage(2, status="planned", depends_on=["stage:1"]),
            stage(3, status="planned"),
            stage(4, status="superseded", superseded_by="stage:3"),
        ]
        _, doc = publish("2705", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["next_actionable_stage_ids"], ["stage:3"])
        candidate_ids = [c["id"] for c in view["active_candidates"]]
        self.assertEqual(candidate_ids, ["stage:1", "stage:2", "stage:3"])
        self.assertNotIn("stage:4", candidate_ids)
        self.assertEqual(view["coverage"]["superseded"], 1)

    def test_st04_terminal_dependencies_gate_actionable(self):
        doc = support.minimal_task("2706")
        doc["stages"] = [
            stage(1, status="verified"),
            stage(2, status="closed"),
            stage(3, status="planned", depends_on=["stage:1", "stage:2"]),
            stage(4, status="planned", depends_on=["stage:3"]),
            stage(5, status="superseded", superseded_by="stage:1"),
            stage(6, status="planned", depends_on=["stage:5"]),
        ]
        _, doc = publish("2706", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["next_actionable_stage_ids"],
                         ["stage:3", "stage:6"])

    def test_latest_documented_ignores_placeholder_with_plan(self):
        doc = support.minimal_task("2707")
        doc["artifacts"] = [
            artifact("art-p2", "plan", "stage:2"),
            artifact("art-p4", "plan", "stage:4"),
            artifact("art-p5", "plan", "stage:5"),
        ]
        doc["stages"] = [
            stage(2, status="active", plan_artifact_id="art-p2"),
            stage(4, status="planned", plan_artifact_id="art-p4"),
            stage(5, status="planned", placeholder=True,
                  plan_artifact_id="art-p5"),
        ]
        _, doc = publish("2707", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["latest_documented_stage_id"], "stage:4")
        self.assertEqual(view["active_stage_id"], "stage:2")
        self.assertEqual(view["next_allocatable_number"], 6)
        self.assertEqual(view["coverage"],
                         {"stages_total": 3, "placeholders": 1,
                          "superseded": 0})

    def test_cards_carry_artifact_counts(self):
        doc = support.minimal_task("2708")
        doc["artifacts"] = [
            artifact("art-d1", "diff", "stage:2"),
            artifact("art-d2", "diff_files", "stage:2"),
        ]
        doc["stages"] = [
            stage(2, status="active",
                  diff_artifact_ids=["art-d1", "art-d2"],
                  test_run_ids=["tr1", "tr2", "tr3"]),
            stage(3, status="planned"),
        ]
        _, doc = publish("2708", doc)
        view = stages.stages_view(doc)
        card_two = next(c for c in view["stages"] if c["id"] == "stage:2")
        self.assertEqual(card_two["diffs"], 2)
        self.assertEqual(card_two["test_runs"], 3)
        self.assertEqual(card_two["title"], "Стадия 2")
        card_three = next(c for c in view["stages"] if c["id"] == "stage:3")
        self.assertEqual(card_three["diffs"], 0)
        self.assertEqual(card_three["test_runs"], 0)

    def test_empty_stages_allocate_one(self):
        doc = support.minimal_task("2709")
        _, doc = publish("2709", doc)
        view = stages.stages_view(doc)
        self.assertEqual(view["next_allocatable_number"], 1)
        self.assertIsNone(view["active_stage_id"])
        self.assertEqual(view["stages"], [])
        self.assertEqual(view["coverage"],
                         {"stages_total": 0, "placeholders": 0,
                          "superseded": 0})


class StageScopeTests(unittest.TestCase):
    def test_task_and_stage_scopes_parse(self):
        self.assertEqual(stages.stage_scope("task"),
                         {"kind": "task", "number": None})
        self.assertEqual(stages.stage_scope("stage:3"),
                         {"kind": "stage", "number": 3})

    def test_invalid_scopes_raise(self):
        for bad in ("", "tasks", "stage", "stage:", "stage:x", "Stage:2",
                    "stage:-1", "stage:2v", " task", "task:1", None, 7):
            with self.assertRaises(stages.StagesError) as ctx:
                stages.stage_scope(bad)
            self.assertEqual(ctx.exception.code, "invalid_scope")


class ResolveStageArtifactsTests(unittest.TestCase):
    def test_scope_exact_resolution_and_manifest(self):
        doc = support.minimal_task("2710")
        doc["artifacts"] = [
            artifact("art-p2", "plan", "stage:2"),
            artifact("art-d2", "diff", "stage:2"),
            artifact("art-df2", "diff_files", "stage:2"),
            artifact("art-tr2", "test_run", "stage:2"),
            artifact("art-ts2", "test_spec", "stage:2"),
            artifact("art-dt", "diff", "task"),
            artifact("art-p3", "plan", "stage:3"),
        ]
        doc["stages"] = [
            stage(2, status="active", plan_artifact_id="art-p2",
                  diff_artifact_ids=["art-d2", "art-df2"],
                  diff_manifest_id="art-d2",
                  test_run_ids=["art-tr2"]),
            stage(3, status="planned", plan_artifact_id="art-p3"),
        ]
        _, doc = publish("2710", doc)
        resolved = stages.resolve_stage_artifacts(doc, "stage:2")
        self.assertEqual(resolved["plan"]["id"], "art-p2")
        self.assertEqual([a["id"] for a in resolved["diffs"]],
                         ["art-d2", "art-df2"])
        self.assertEqual(resolved["manifest"]["id"], "art-d2")
        self.assertEqual([a["id"] for a in resolved["tests"]],
                         ["art-tr2", "art-ts2"])
        stage_three = stages.resolve_stage_artifacts(doc, "stage:3")
        self.assertEqual(stage_three["plan"]["id"], "art-p3")
        self.assertEqual(stage_three["diffs"], [])
        self.assertIsNone(stage_three["manifest"])
        self.assertEqual(stage_three["tests"], [])

    def test_unknown_stage_raises(self):
        doc = support.minimal_task("2711")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.resolve_stage_artifacts(doc, "stage:9")
        self.assertEqual(ctx.exception.code, "unknown_stage")


class LegacyFolderTests(unittest.TestCase):
    def test_parses_stage_and_variant_folders(self):
        root, docs = support.make_docs()
        task_dir = docs / "tasks" / "2712"
        for name in ("stage2", "stage1v2", "stage6", "stageplan", "notes"):
            (task_dir / name).mkdir(parents=True)
        (task_dir / "task.json").write_text("{}", encoding="utf-8")
        records = stages.legacy_stage_folders(docs, "2712")
        parsed = [(r["number"], r["variant"]) for r in records]
        self.assertEqual(parsed, [(1, 2), (2, None), (6, None)])
        for record in records:
            self.assertIsInstance(record["path"], Path)
            self.assertTrue(record["path"].is_dir())
            self.assertEqual(record["path"].parent, task_dir)

    def test_missing_task_dir_returns_empty(self):
        root, docs = support.make_docs()
        self.assertEqual(stages.legacy_stage_folders(docs, "2713"), [])


if __name__ == "__main__":
    unittest.main()
