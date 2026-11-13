"""GT01-GT05 git containment tests (offline real git repos in sandbox)."""

import subprocess
import unittest

import support
from jsondoc import ingest
from jsondoc.store import Store


def git(repo, *argv):
    env = {"GIT_AUTHOR_NAME": "QA", "GIT_AUTHOR_EMAIL": "qa@example.test",
           "GIT_COMMITTER_NAME": "QA",
           "GIT_COMMITTER_EMAIL": "qa@example.test",
           "GIT_CEILING_DIRECTORIES": str(repo.parent)}
    proc = subprocess.run(["git"] + list(argv), cwd=str(repo), env=env,
                          capture_output=True)
    return proc


def init_repo(release_after_task=True):
    root, docs = support.make_docs()
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "master")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "features/#42")
    (repo / "task.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "#42 feat one")
    (repo / "task.txt").write_text("two\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "#42 feat two")
    git(repo, "checkout", "master")
    if release_after_task:
        git(repo, "merge", "--no-ff", "features/#42", "-m", "merge task")
        git(repo, "branch", "release/5.6.1")
    else:
        git(repo, "branch", "release/5.6.1")
        git(repo, "merge", "--no-ff", "features/#42", "-m", "merge task")
    git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
    git(repo, "branch", "bugfixes/#42_for5606")
    return repo, root, docs


def task_oids(repo):
    proc = git(repo, "log", "--no-merges", "--reverse",
               "--format=%H%x09%s", "master")
    oids = []
    for line in proc.stdout.decode().splitlines():
        oid, subject = line.split("\t", 1)
        if subject.startswith("#42"):
            oids.append(oid)
    return oids


class GitStateTests(unittest.TestCase):
    def test_unmatched_branches_diagnosed(self):
        repo, root, docs = init_repo()
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        # master/features are containing refs that match no release pattern
        self.assertIn("master", state["unmatched_branches"])
        self.assertNotIn("release/5.6.1", state["unmatched_branches"])
        # empty release_branches is distinguishable from pattern mismatch
        if not state["release_branches"]:
            self.assertTrue(state["unmatched_branches"])

    def test_gt01_full_containment(self):
        repo, root, docs = init_repo(release_after_task=True)
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        self.assertIn("origin/master", state["pushed_to"])
        self.assertIn("release/5.6.1", state["release_branches"])
        self.assertNotIn("bugfixes/#42_for5606", state["release_branches"])

    def test_gt01_partial_containment(self):
        repo, root, docs = init_repo(release_after_task=False)
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        self.assertIn("origin/master", state["pushed_to"])
        self.assertNotIn("release/5.6.1", state["release_branches"])

    def test_gt03_unknown_tip_not_claimed(self):
        repo, root, docs = init_repo()
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        self.assertNotIn("nonexistent", state["pushed_to"])
        git_ing = ingest.GitIngest(repo)
        self.assertEqual(git_ing.is_ancestor(task_oids(repo)[0],
                                             "no-such-ref"), "unknown")

    def test_gt05_backport_branch_not_release(self):
        repo, root, docs = init_repo()
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        pool = state["pushed_to"] + state["contained_in"]
        self.assertEqual(state["release_branches"],
                         [r for r in pool if r.startswith("release/")])

    def test_gt04_cherry_pick_not_false_claim(self):
        repo, root, docs = init_repo(release_after_task=False)
        # cherry-pick the first task commit onto release branch
        git(repo, "checkout", "release/5.6.1")
        git(repo, "cherry-pick", task_oids(repo)[0], "--allow-empty")
        git(repo, "checkout", "master")
        state = ingest.build_git_state(repo, task_oids(repo), ["release/*"])
        self.assertNotIn("release/5.6.1", state["release_branches"])


class IngestGitTests(unittest.TestCase):
    def seeded_store(self):
        root, docs = support.make_docs()
        store = Store(root, docs)
        doc = support.minimal_task("42", "Задача")
        envelope = {"schema_version": "1.0", "operation_id": "c42",
                    "expected_revision": 0, "actor": "user", "reason": "seed",
                    "operations": [], "document": doc}
        store.apply("task", "42", envelope)
        return root, docs, store

    def apply_events(self, store, repo, oids):
        sup = support
        doc = store.load("task", "42")
        envelope = {"schema_version": "1.0",
                    "operation_id": "events-42",
                    "expected_revision": doc["revision"], "actor": "task-diff",
                    "reason": "register commits",
                    "operations": [
                        {"op": "upsert", "collection": "git_events",
                         "key": "G1",
                         "value": {"id": "G1", "action": "commit",
                                   "commit": oids[0],
                                   "branch": "features/#42", "remote": None,
                                   "source_ids": [], "observed_at": None}},
                        {"op": "upsert", "collection": "git_events",
                         "key": "G2",
                         "value": {"id": "G2", "action": "commit",
                                   "commit": oids[1],
                                   "branch": "features/#42", "remote": None,
                                   "source_ids": [], "observed_at": None}}],
                    "document": None}
        store.apply("task", "42", envelope)

    def test_apply_sets_git_state_then_noop(self):
        repo, root, docs = init_repo()
        root2, docs2, store = self.seeded_store()
        oids = task_oids(repo)
        self.apply_events(store, repo, oids)
        result = ingest.ingest_git(store, "42", repo, ["release/*"])
        self.assertEqual(result["status"], "applied")
        state = store.load("task", "42")["git_state"]
        self.assertEqual(state["commit"], oids[-1])
        self.assertIn("origin/master", state["pushed_to"])
        again = ingest.ingest_git(store, "42", repo, ["release/*"])
        self.assertEqual(again["status"], "noop")

    def test_no_commits_unknown(self):
        repo, root, docs = init_repo()
        root2, docs2, store = self.seeded_store()
        result = ingest.ingest_git(store, "42", repo, ["release/*"])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["errors"][0]["code"], "no_commits")


if __name__ == "__main__":
    unittest.main()
