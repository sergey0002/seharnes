"""J07 stage diff tests: fixed git argv adapter, ownership checks,
manifest determinism, workspace delta. All inside the selftest sandbox,
offline, no network, no live task folders."""

import subprocess
import unittest
from pathlib import Path

import support
from jsondoc import stages


def git(repo, *argv):
    proc = subprocess.run(["git"] + list(argv), cwd=str(repo),
                          capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"git {list(argv)} failed: "
            f"{proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace")


def init_repo():
    root, docs = support.make_docs()
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "checkout", "-b", "master")
    git(repo, "config", "user.email", "qa@example.test")
    git(repo, "config", "user.name", "QA Robot")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "A.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", "A.txt")
    git(repo, "commit", "-m", "base commit")
    base_oid = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-b", "task-branch")
    (repo / "B.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "B.txt")
    git(repo, "commit", "-m", "#77 feat one")
    oid_one = git(repo, "rev-parse", "HEAD").strip()
    (repo / "C.txt").write_text("two\n", encoding="utf-8")
    git(repo, "add", "C.txt")
    git(repo, "commit", "-m", "#77 feat two")
    oid_two = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-b", "other-branch", "master")
    (repo / "D.txt").write_text("other\n", encoding="utf-8")
    git(repo, "add", "D.txt")
    git(repo, "commit", "-m", "other")
    oid_other = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-b", "mixed-branch")
    (repo / "E.txt").write_text("three\n", encoding="utf-8")
    git(repo, "add", "E.txt")
    git(repo, "commit", "-m", "#77 feat three")
    oid_three = git(repo, "rev-parse", "HEAD").strip()
    return {
        "repo": repo,
        "base_oid": base_oid,
        "oid_one": oid_one,
        "oid_two": oid_two,
        "oid_other": oid_other,
        "oid_three": oid_three,
    }


PLAN_SHA = "b" * 64


class GitAdapterTests(unittest.TestCase):
    def test_git_repo_ok_false_for_non_repo(self):
        root, _docs = support.make_docs()
        plain = root / "not-a-repo"
        plain.mkdir(parents=True)
        self.assertFalse(stages.git_repo_ok(plain))
        fixture = init_repo()
        self.assertTrue(stages.git_repo_ok(fixture["repo"]))

    def test_resolve_oid_known_and_missing_ref(self):
        fixture = init_repo()
        oid = stages.resolve_oid(fixture["repo"], "task-branch")
        self.assertEqual(oid, fixture["oid_two"])
        self.assertRegex(oid, r"^[0-9a-f]{40}$")
        self.assertIsNone(stages.resolve_oid(fixture["repo"], "no-such-ref"))

    def test_workspace_delta_lists_tracked_modifications_only(self):
        fixture = init_repo()
        repo = fixture["repo"]
        git(repo, "checkout", "task-branch")
        (repo / "A.txt").write_text("base changed\n", encoding="utf-8")
        (repo / "U.txt").write_text("untracked\n", encoding="utf-8")
        delta = stages.workspace_delta(repo)
        self.assertIn("A.txt", delta)
        self.assertNotIn("U.txt", delta)

    def test_commits_between_respects_path_scope(self):
        fixture = init_repo()
        commits = stages.commits_between(fixture["repo"],
                                         fixture["base_oid"],
                                         "task-branch", path_scope="B.txt")
        self.assertEqual([c["oid"] for c in commits], [fixture["oid_one"]])
        self.assertEqual(commits[0]["subject"], "#77 feat one")


class StageDiffManifestTests(unittest.TestCase):
    def test_st05_explicit_oids_select_exactly_own_commits(self):
        fixture = init_repo()
        commits = stages.commits_between(fixture["repo"],
                                         fixture["base_oid"], "task-branch")
        self.assertEqual([c["oid"] for c in commits],
                         [fixture["oid_one"], fixture["oid_two"]])
        self.assertEqual([c["subject"] for c in commits],
                         ["#77 feat one", "#77 feat two"])
        manifest = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 2, "commits",
            commit_oids=[fixture["oid_one"], fixture["oid_two"]],
            source_plan_sha256=PLAN_SHA)
        self.assertEqual(manifest["task_id"], "77")
        self.assertEqual(manifest["stage_id"], "stage:2")
        self.assertEqual(manifest["selection_mode"], "commits")
        self.assertEqual(manifest["commit_oids"],
                         [fixture["oid_one"], fixture["oid_two"]])
        self.assertEqual(manifest["source_plan_sha256"], PLAN_SHA)
        self.assertEqual(manifest["coverage"]["commits_selected"], 2)
        self.assertEqual(sorted(manifest["files"]), ["B.txt", "C.txt"])
        self.assertEqual(manifest["coverage"]["paths_touched"], 2)
        self.assertEqual(manifest["coverage"]["uncommitted_files"], 0)
        self.assertRegex(manifest["diff_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["files_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["generated_at"],
                         r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:"
                         r"[0-9]{2}Z$")

    def test_st06_stage_manifest_excludes_unrelated_commit(self):
        fixture = init_repo()
        manifest = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 2, "range",
            base=fixture["base_oid"], head="task-branch",
            source_plan_sha256=PLAN_SHA)
        self.assertNotIn(fixture["oid_other"], manifest["commit_oids"])
        subjects = set(manifest["ownership_evidence"]["subjects"].values())
        self.assertEqual(subjects, {"#77 feat one", "#77 feat two"})
        self.assertEqual(manifest["ownership_evidence"]
                         ["unowned_commit_oids"], [])
        self.assertIn("net_diff_sha256", manifest)
        self.assertEqual(manifest["base_oid"], fixture["base_oid"])
        self.assertEqual(manifest["head_oid"], fixture["oid_two"])

    def test_st07_foreign_commit_in_range_requires_exclusions(self):
        fixture = init_repo()
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(
                fixture["repo"], "77", 3, "range",
                base=fixture["base_oid"], head="mixed-branch",
                source_plan_sha256=PLAN_SHA)
        self.assertEqual(ctx.exception.code, "stage_diff_range_mixed")
        unowned = ctx.exception.payload["unowned"]
        self.assertEqual([c["oid"] for c in unowned], [fixture["oid_other"]])
        self.assertEqual(unowned[0]["subject"], "other")

        manifest = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 3, "range",
            base=fixture["base_oid"], head="mixed-branch",
            source_plan_sha256=PLAN_SHA,
            exclusions=[fixture["oid_other"]])
        self.assertEqual(manifest["commit_oids"], [fixture["oid_three"]])
        self.assertEqual(manifest["coverage"]["commits_selected"], 1)
        self.assertEqual(manifest["coverage"]["excluded_commits"],
                         [fixture["oid_other"]])
        subjects = set(manifest["ownership_evidence"]["subjects"].values())
        self.assertEqual(subjects, {"#77 feat three"})
        self.assertEqual(manifest["ownership_evidence"]
                         ["excluded_commit_oids"], [fixture["oid_other"]])

    def test_manifest_hashes_deterministic(self):
        fixture = init_repo()
        kwargs = {
            "commit_oids": [fixture["oid_one"], fixture["oid_two"]],
            "source_plan_sha256": PLAN_SHA,
        }
        first = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 2, "commits", **kwargs)
        second = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 2, "commits", **kwargs)
        self.assertEqual(first["diff_sha256"], second["diff_sha256"])
        self.assertEqual(first["files_sha256"], second["files_sha256"])
        self.assertEqual(first["commit_oids"], second["commit_oids"])
        self.assertEqual(first["files"], second["files"])
        third = stages.build_stage_diff_manifest(
            fixture["repo"], "77", 2, "commits",
            commit_oids=[fixture["oid_two"], fixture["oid_one"]],
            source_plan_sha256=PLAN_SHA)
        self.assertNotEqual(third["diff_sha256"], first["diff_sha256"])

    def test_workspace_delta_manifest_hashes_dirty_files(self):
        fixture = init_repo()
        repo = fixture["repo"]
        git(repo, "checkout", "task-branch")
        (repo / "A.txt").write_text("base changed\n", encoding="utf-8")
        manifest = stages.build_stage_diff_manifest(
            repo, "77", 1, "workspace_delta", source_plan_sha256=PLAN_SHA)
        self.assertEqual(manifest["commit_oids"], [])
        self.assertEqual(manifest["coverage"]["commits_selected"], 0)
        self.assertEqual(manifest["coverage"]["uncommitted_files"], 1)
        entry = manifest["uncommitted"][0]
        self.assertEqual(entry["path"], "A.txt")
        self.assertRegex(entry["old_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(entry["new_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotEqual(entry["old_sha256"], entry["new_sha256"])
        self.assertEqual(manifest["files"], ["A.txt"])
        self.assertEqual(manifest["base_oid"], fixture["oid_two"])
        self.assertIsNone(manifest["head_oid"])

    def test_invalid_inputs_raise_stages_errors(self):
        fixture = init_repo()
        repo = fixture["repo"]
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "77", 2, "bogus")
        self.assertEqual(ctx.exception.code, "invalid_selection_mode")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "77", 2, "commits")
        self.assertEqual(ctx.exception.code, "commits_required")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "77", 2, "range",
                                             base="master")
        self.assertEqual(ctx.exception.code, "range_refs_required")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "77", 2, "range",
                                             base="master", head="ghost")
        self.assertEqual(ctx.exception.code, "range_ref_unresolved")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "abc", 2, "commits",
                                             commit_oids=[fixture["oid_one"]])
        self.assertEqual(ctx.exception.code, "invalid_task_key")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(repo, "77", 0, "commits",
                                             commit_oids=[fixture["oid_one"]])
        self.assertEqual(ctx.exception.code, "invalid_stage_number")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.build_stage_diff_manifest(
                repo, "77", 2, "commits",
                commit_oids=[fixture["oid_one"]], source_plan_sha256="zz")
        self.assertEqual(ctx.exception.code, "invalid_source_plan_sha256")

    def test_artifact_diff_id_convention(self):
        files_sha = "c" * 64
        self.assertEqual(
            stages.artifact_diff_id("2612", 2, files_sha),
            f"artifact:2612:stage:2:diff:{'c' * 12}")
        with self.assertRaises(stages.StagesError) as ctx:
            stages.artifact_diff_id("2612", 2, "short")
        self.assertEqual(ctx.exception.code, "invalid_files_sha256")


if __name__ == "__main__":
    unittest.main()
