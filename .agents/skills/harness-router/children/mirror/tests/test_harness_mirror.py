#!/usr/bin/env python3
"""Tests for harness_mirror. Run: python3 -m pytest .agents/skills/harness-router/children/mirror/tests/test_harness_mirror.py -q"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT_DIR = HERE.parent / "scripts"


def load_module():
    spec = importlib.util.spec_from_file_location("harness_mirror", SCRIPT_DIR / "harness_mirror.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hm = load_module()


def args(**kw):
    base = dict(root=None, data=".agents/skills/harness-router/children/mirror/.data", paths=[], include_mirrors=False,
                include_dsh=False, force=False, node=None, json=None, model=None,
                block=None, content=None)
    base.update(kw)
    return type("Args", (), base)


def write(path: Path, text: str, bom: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ("\ufeff" if bom else "") + text
    path.write_bytes(data.encode("utf-8"))
    return path


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    write(tmp_path / ".doc" / "rules.md", "# Rules\n\nRead this first.\n")
    write(
        tmp_path / ".cursor" / "rules" / "doc-rules.mdc",
        "---\ndescription: rules\nalwaysApply: true\n---\n\n# Rules\n\nRead `.doc/rules.md` first.\n",
    )
    write(
        tmp_path / ".cursor" / "skills" / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: demo skill\n---\n\n# Demo\n\nUse when the user says demo.\n\nRun `.cursor/rules/doc-rules.mdc`.\n",
    )
    write(tmp_path / ".antigravity" / "skills" / "demo" / "SKILL.md",
          (tmp_path / ".cursor" / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8"))
    write(tmp_path / ".cursor" / "scripts" / "run.sh", "#!/usr/bin/env bash\necho hi\n")
    write(tmp_path / ".cursor" / "mcp.env", "TOKEN=secret\n")
    return tmp_path


def scan(root: Path, **kw):
    data = (root / ".cursor" / "skills" / "harness-mirror" / ".data").resolve()
    return hm.cmd_scan(args(**kw), root, data)


def data_of(root: Path) -> Path:
    return (root / ".cursor" / "skills" / "harness-mirror" / ".data").resolve()


def test_markdown_roundtrip_with_frontmatter():
    text = "---\nname: demo\n---\n\n# Title\n\nBody.\n\n## Section\n\n- one\n- two\n\n### Deep\n\nTail\n"
    blocks = hm.split_markdown(text)
    assert blocks[0]["block_type"] == "frontmatter"
    assert "".join(b["raw_content"] for b in blocks) == text
    assert [b["header_text"] for b in blocks if b["block_type"] == "section"] == ["Title", "Section", "Deep"]


def test_markdown_roundtrip_crlf_and_no_final_newline():
    text = "---\r\nname: x\r\n---\r\n\r\n# H\r\n\r\ntext"
    blocks = hm.split_markdown(text)
    assert "".join(b["raw_content"] for b in blocks) == text
    assert hm.line_ending_of(text) == "\r\n"
    assert not text.endswith("\n")


def test_markdown_mixed_endings():
    text = "# A\r\n\ntext\n"
    assert hm.line_ending_of(text) == "mixed"


def test_code_roundtrip():
    text = "#!/usr/bin/env python3\nimport os\n\n\ndef one():\n    return 1\n\n\ndef two():\n    return 2\n"
    blocks = hm.split_code(text)
    assert "".join(b["raw_code"] for b in blocks) == text
    assert "one" in [b["name_or_purpose"] for b in blocks]


def test_environment_and_ids():
    assert hm.environment_of(".cursor/rules/x.mdc") == "cursor"
    assert hm.environment_of(".antigravity/rules/x.mdc") == "antigravity"
    assert hm.environment_of(".dsh/project.patch.yml") == "dsh"
    assert hm.node_id_of(".agents/skills/documentation-router/children/task-doc/SKILL.md") == "skill:task-doc"
    assert hm.node_id_of(".antigravity/skills/task-doc/SKILL.md") == "skill:task-doc@antigravity"
    assert hm.node_id_of(".kilo/rules/doc-rules.md") == "rule:doc-rules@kilo"
    assert hm.node_id_of(".agents/skills/a/README.md") != hm.node_id_of(".agents/skills/a/SKILL.md")
    assert hm.node_id_of(".cursor/scripts/x.sh") != hm.node_id_of(".cursor/scripts/x.js")
    assert hm.is_canonical_rel(".agents/skills/a/SKILL.md") is True
    assert hm.is_canonical_rel(".agents/rules/a.md") is False
    assert hm.node_id_of(".agents/rules/a.md") == "rule:a@agents"


def test_agents_skills_tree_is_canonical(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".agents" / "skills" / "agents-only" / "SKILL.md",
        "---\nname: agents-only\ndescription: agents skill\n---\n\n# Agents only\n",
    )
    scan(root)
    data = data_of(root)
    node = json.loads((data / "nodes" / "skill__agents-only.json").read_text(encoding="utf-8"))
    assert node["meta"]["canonical"] is True
    assert node["meta"]["projection_of"] is None
    assert node["meta"]["source_file_path"] == ".agents/skills/agents-only/SKILL.md"


def test_mcp_server_copies_are_not_projections(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "mcp-servers" / "tool" / "server.js", "console.log('.cursor/tools');\n")
    write(root / ".codex" / "mcp-servers" / "tool" / "server.js", "console.log('.codex/tools');\n")
    scan(root, include_mirrors=True)
    data = data_of(root)
    nodes = [json.loads(path.read_text(encoding="utf-8"))
             for path in (data / "nodes").glob("*.json")]
    mirror = next(n for n in nodes
                  if n["meta"]["source_file_path"] == ".codex/mcp-servers/tool/server.js")
    assert mirror["meta"]["canonical"] is False
    assert mirror["meta"]["projection_of"] is None


def test_scan_build_check(tmp_path, capsys):
    root = make_repo(tmp_path)
    assert scan(root, include_mirrors=True) == 0
    data = data_of(root)
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    assert node["meta"]["canonical"] is True
    assert node["meta"]["projection_of"] is None
    assert node["meta"]["transferable"] is True
    assert "repo_relative_path" not in node["meta"]
    assert node["reconstruction_meta"]["final_newline"] is True
    assert "at" not in node["analysis"]
    assert hm.compile_node(node) == (root / ".cursor" / "rules" / "doc-rules.mdc").read_text(encoding="utf-8")
    assert hm.cmd_build(args(), root, data) == 0
    assert hm.cmd_check(args(), root, data) == 0
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    assert graph["stats"]["nodes"] == 4
    assert graph["stats"]["mirrors"] == 1


def test_visibility_contract_across_adapters(tmp_path):
    root = tmp_path
    rules = root / ".cursor" / "rules"
    write(rules / "gates.mdc",
          "---\ndescription: hard gates\nalwaysApply: true\ngate: true\n---\n\n# Gates\n")
    write(rules / "path-rule.mdc",
          "---\ndescription: path rule\nglobs:\n  - '**/*.md'\nattach: glob\nalwaysApply: false\n---\n\n# Path rule\n")

    write(root / ".kilo" / "kilo.jsonc",
          '{"instructions":[".kilo/rules/gates.md"]}\n')
    write(root / ".kilo" / "rules-index.md",
          "<!-- glob-triggers -->\n`**/*.md`\n")
    write(root / ".codex" / "rules-index.md",
          "## Обязательные (alwaysApply: true)\n`.codex/rules/gates.md`\n"
          "## По требованию\n<!-- glob-triggers -->\n`**/*.md`\n")
    write(root / "AGENTS.md", "<!-- harness-gate: gates -->\n# Gates\n")
    write(root / "DSH-RULES.md",
          "<!-- rule: gates (always) -->\n## On-demand rules\n<!-- glob-triggers -->\n`**/*.md`\n")

    for directory, always_trigger, path_trigger in (
        (".qoder/rules", "always_on", "glob"),
        (".agents/rules", "always_on", "glob"),
    ):
        write(root / directory / "gates.md", f"---\ntrigger: {always_trigger}\n---\n")
        write(root / directory / "path-rule.md", f"---\ntrigger: {path_trigger}\n---\n")
    write(root / ".qwen" / "rules" / "gates.md", "---\ndescription: gates\n---\n")
    write(root / ".qwen" / "rules" / "path-rule.md",
          "---\ndescription: path rule\npaths:\n  - '**/*.md'\n---\n")

    report = hm.compute_visibility(root)
    assert report["status"] == "passed", report["errors"]
    assert report["matrix"]["gates"]["kilo"] == "inline"
    assert report["matrix"]["path-rule"]["qwen"] == "glob"

    (root / "AGENTS.md").unlink()
    report = hm.compute_visibility(root)
    assert any("gate not inline in codex" in error for error in report["errors"])
    write(root / "AGENTS.md", "<!-- harness-gate: gates -->\n# Gates\n")

    (root / ".qwen" / "rules" / "gates.md").unlink()
    report = hm.compute_visibility(root)
    assert report["status"] == "failed"
    assert any("gate not inline in qwen" in error for error in report["errors"])


def test_secret_files_are_skipped(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    cache = json.loads((data_of(root) / "cache.map").read_text(encoding="utf-8"))
    assert ".cursor/mcp.env" not in cache


def test_mirror_inherits_canon_analysis(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    analysis = {"description": "rules", "lifecycle": {"trigger_condition": "always", "phase": "pre-execution"}}
    payload = data / "analysis.json"
    payload.write_text(json.dumps(analysis), encoding="utf-8")
    assert hm.cmd_apply(args(node="rule:doc-rules", json=str(payload)), root, data) == 0
    # mirror has no canon counterpart in .cursor for .antigravity/rules, so force a skill mirror only
    mirror = json.loads((data / "nodes" / "skill__demo__antigravity.json").read_text(encoding="utf-8"))
    assert mirror["meta"]["projection_of"] == "skill:demo"
    assert mirror["meta"]["canonical"] is False


def test_incremental_scan(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    out = scan(root)
    assert out == 0
    cache = json.loads((data_of(root) / "cache.map").read_text(encoding="utf-8"))
    assert len(cache) == 3


def test_apply_rejects_bad_anchor_and_auto_origin(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    for payload in (
        {"relations": [{"block_id": "b002", "target_name": "x", "target_type": "skill", "relation_type": "delegates_to", "origin": "agent", "resolution": "unresolved", "anchor_text": "absent"}]},
        {"relations": [{"block_id": "b002", "target_name": "x", "target_type": "skill", "relation_type": "delegates_to", "origin": "auto", "resolution": "unresolved", "anchor_text": "Rules"}]},
        {"relations": [{"block_id": "nope", "target_name": "x", "target_type": "skill", "relation_type": "delegates_to", "origin": "agent", "resolution": "unresolved", "anchor_text": "Rules"}]},
    ):
        path = data / "bad.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert hm.cmd_apply(args(node="rule:doc-rules", json=str(path)), root, data) == 1


def test_set_refuses_mirror(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    node = json.loads((data / "nodes" / "skill__demo__antigravity.json").read_text(encoding="utf-8"))
    block = node["content_blocks"][1]["block_id"]
    content = data / "block.md"
    content.write_text("# Demo\n\nnew\n", encoding="utf-8")
    assert hm.cmd_set(args(node="skill:demo@antigravity", block=block, content=str(content)), root, data) == 1


def test_set_rewrites_canonical(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    block = next(b for b in node["content_blocks"] if b["header_text"] == "Rules")
    content = data / "block.md"
    content.write_text("# Rules\n\nRead `.doc/rules.md` first, then nothing.\n", encoding="utf-8")
    assert hm.cmd_set(args(node="rule:doc-rules", block=block["block_id"], content=str(content)), root, data) == 0
    assert "then nothing" in (root / ".cursor" / "rules" / "doc-rules.mdc").read_text(encoding="utf-8")
    assert list((data / "nodes" / ".history").glob("*.json"))


def test_bom_and_final_newline(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "rules" / "bom.mdc", "---\ndescription: b\n---\n\n# B\n", bom=True)
    scan(root)
    node = json.loads((data_of(root) / "nodes" / "rule__bom.json").read_text(encoding="utf-8"))
    assert node["reconstruction_meta"]["bom"] is True
    assert hm.compile_node(node) == (root / ".cursor" / "rules" / "bom.mdc").read_text(encoding="utf-8-sig")
    assert hm.cmd_check(args(), root, data_of(root)) == 0


def test_build_is_deterministic(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    first = hashlib.sha256((data / "graph.json").read_bytes()).hexdigest()
    hm.cmd_build(args(), root, data)
    second = hashlib.sha256((data / "graph.json").read_bytes()).hexdigest()
    assert first == second


def test_root_detection_from_script(tmp_path):
    root = make_repo(tmp_path)
    script = root / ".kilo" / "skills" / "harness-mirror" / "scripts" / "harness_mirror.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    assert hm.find_root(None, script) == root.resolve()


def test_drift_is_reported(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    mirror = root / ".antigravity" / "skills" / "demo" / "SKILL.md"
    mirror.write_text(mirror.read_text(encoding="utf-8") + "\nextra line\n", encoding="utf-8")
    scan(root, include_mirrors=True)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    assert graph["stats"]["drift"] >= 1


def test_skill_slug_does_not_collide(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "skills" / "one" / "references" / "index.md", "# One\n")
    write(root / ".cursor" / "skills" / "two" / "references" / "index.md", "# Two\n")
    assert scan(root) == 0
    ids = {
        json.loads(path.read_text(encoding="utf-8"))["meta"]["node_id"]
        for path in (data_of(root) / "nodes").glob("doc__*.json")
    }
    assert "doc:one-references" in ids
    assert "doc:two-references" in ids


def test_schema_version_bump_forces_reparse(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    cache_path = data_of(root) / "cache.map"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for entry in cache.values():
        entry["schema_version"] = "0.0"
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    assert scan(root) == 0
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert {entry["schema_version"] for entry in cache.values()} == {hm.SCHEMA_VERSION}


def test_missing_target_keeps_path(tmp_path):
    root = make_repo(tmp_path)
    notes = root / ".cursor" / "skills" / "demo" / "references" / "notes.md"
    shared = root / ".cursor" / "skills" / "demo" / "references" / "shared.md"
    write(shared, "# Shared\n")
    write(notes, "# Notes\n\nSee `shared.md`.\n")
    scan(root)
    data = data_of(root)
    node_file = data / "nodes" / "doc__demo-notes.json"

    def shared_relation():
        node = json.loads(node_file.read_text(encoding="utf-8"))
        return next(
            r for b in node["content_blocks"] for r in b["relations"] if r["target_name"] == "shared.md"
        )

    assert shared_relation()["resolution"] == "resolved"
    shared.unlink()
    scan(root)
    relation = shared_relation()
    assert relation["resolution"] == "missing"
    assert relation["target_path"].endswith("shared.md")
    assert hm.cmd_check(args(), root, data) == 0

    node = json.loads(node_file.read_text(encoding="utf-8"))
    for block in node["content_blocks"]:
        for rel in block["relations"]:
            if rel["target_name"] == "shared.md":
                rel["resolution"] = "unresolved"
    node_file.write_text(json.dumps(node), encoding="utf-8")
    assert hm.cmd_check(args(), root, data) == 1


def test_apply_rejects_resolved_target_outside_index(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    payload = {
        "relations": [{
            "block_id": "b002", "target_name": "absent", "target_type": "skill",
            "relation_type": "delegates_to", "origin": "agent", "resolution": "resolved",
            "target_node_id": "skill:absent", "anchor_text": "Rules",
        }]
    }
    path = data / "analysis-bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert hm.cmd_apply(args(node="rule:doc-rules", json=str(path)), root, data) == 1


def test_set_rebuilds_graph(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    block = next(b for b in node["content_blocks"] if b["header_text"] == "Rules")
    content = data / "block.md"
    content.write_text("# Rules\n\nRead `.doc/rules.md` and `.agents/skills/demo/SKILL.md`.\n", encoding="utf-8")
    assert hm.cmd_set(args(node="rule:doc-rules", block=block["block_id"], content=str(content)), root, data) == 0
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    assert any(
        edge["source"] == "rule:doc-rules" and edge["target"] == "skill:demo"
        for edge in graph["edges"]
    )


def test_documentation_is_outside_harness(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".doc" / "harnes" / "doc_rules.md", "# Harness rules\n\nDocumentation only.\n")
    write(root / ".doc" / "architecture" / "index.md", "# Arch\n")
    scan(root)
    data = data_of(root)
    cache = json.loads((data / "cache.map").read_text(encoding="utf-8"))
    assert not [path for path in cache if path.startswith(".doc/")]
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    relations = [rel for block in node["content_blocks"] for rel in block.get("relations", [])]
    assert not [rel for rel in relations if (rel.get("target_path") or "").startswith(".doc/")]
    assert not [rel for rel in relations if rel.get("target_name") in ("rules.md", "doc_rules.md")]
    assert hm.cmd_check(args(), root, data) == 0


def test_documentation_dropped_from_existing_nodes(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".doc" / "harnes" / "doc_rules.md", "# Harness rules\n")
    scan(root)
    data = data_of(root)
    node_file = data / "nodes" / "rule__doc-rules.json"
    node = json.loads(node_file.read_text(encoding="utf-8"))
    block = node["content_blocks"][-1]
    block["relations"].append({
        "target_name": "doc_rules.md",
        "target_type": "doc",
        "target_path": ".doc/harnes/doc_rules.md",
        "target_node_id": "doc:harnes-doc_rules",
        "relation_type": "reads_context",
        "origin": "auto",
        "resolution": "resolved",
        "anchor_text": "",
        "execution_moment": "",
    })
    node_file.write_text(json.dumps(node), encoding="utf-8")
    scan(root)
    node = json.loads(node_file.read_text(encoding="utf-8"))
    assert not [
        rel for b in node["content_blocks"] for rel in b["relations"]
        if (rel.get("target_path") or "").startswith(".doc/")
    ]
    assert hm.cmd_check(args(), root, data) == 0


def test_check_rejects_relation_outside_harness(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".doc" / "rules.md", "# Rules\n")
    scan(root)
    data = data_of(root)
    node_file = data / "nodes" / "rule__doc-rules.json"
    node = json.loads(node_file.read_text(encoding="utf-8"))
    node["content_blocks"][-1]["relations"].append({
        "target_name": "rules.md",
        "target_type": "doc",
        "target_path": ".doc/rules.md",
        "target_node_id": "doc:rules",
        "relation_type": "reads_context",
        "origin": "auto",
        "resolution": "resolved",
        "anchor_text": "",
        "execution_moment": "",
    })
    node_file.write_text(json.dumps(node), encoding="utf-8")
    assert hm.cmd_check(args(), root, data) == 1


def test_set_file_replaces_skill_and_rule(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    skill = "---\nname: demo\ndescription: demo skill\n---\n\n# Demo\n\nNew body.\n"
    assert hm.set_file(root, data, "skill:demo", skill)["status"] == "ok"
    assert (root / ".cursor" / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8") == skill
    rule = "---\ndescription: rules\n---\n\n# Rules\n\nWhole file.\n"
    assert hm.set_file(root, data, "rule:doc-rules", rule)["status"] == "ok"
    assert (root / ".cursor" / "rules" / "doc-rules.mdc").read_text(encoding="utf-8") == rule
    assert hm.cmd_check(args(), root, data) == 0
    assert list((data / "nodes" / ".history").glob("*.json"))


def test_set_file_refuses_script_and_mirror(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    for node_id in ("script:run-sh", "skill:demo@antigravity"):
        script = node_id.startswith("script:")
        try:
            hm.set_file(root, data, node_id, "# nope\n")
        except hm.MirrorError as exc:
            assert exc.code == 1
            if script:
                assert "editable types" in str(exc)
        else:
            raise AssertionError("only skills and rules may be written: " + node_id)


def test_set_file_keeps_crlf(tmp_path):
    root = make_repo(tmp_path)
    source = root / ".cursor" / "skills" / "demo" / "SKILL.md"
    source.write_bytes(b"---\r\nname: demo\r\n---\r\n\r\n# Demo\r\n\r\nBody.\r\n")
    scan(root)
    data = data_of(root)
    hm.set_file(root, data, "skill:demo", "---\nname: demo\n---\n\n# Demo\n\nEdited.\n")
    raw = source.read_bytes()
    assert b"\r\n" in raw
    assert b"Edited." in raw
    assert hm.compile_node(json.loads((data / "nodes" / "skill__demo.json").read_text(encoding="utf-8"))) == raw.decode("utf-8")


def test_frontmatter_description_becomes_summary(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "skills" / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: >\n  Делает демо.\n  Только факты.\n---\n\n# Demo\n\nBody.\n",
    )
    scan(root)
    data = data_of(root)
    node = json.loads((data / "nodes" / "skill__demo.json").read_text(encoding="utf-8"))
    assert node["meta"]["description"].startswith("Делает демо.")
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    demo = next(n for n in graph["nodes"] if n["id"] == "skill:demo")
    assert demo["summary"].startswith("Делает демо")
    assert "Только факты" in demo["details"]


def test_apply_stores_summary_and_details(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    payload = {"summary": "Проверяет правило", "details": "Запускается перед правкой. Только факты."}
    path = data / "analysis-summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert hm.cmd_apply(args(node="rule:doc-rules", json=str(path)), root, data) == 0
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    assert node["analysis"]["summary"] == "Проверяет правило"
    assert node["analysis"]["details"].startswith("Запускается")

    bad = data / "analysis-long.json"
    bad.write_text(json.dumps({"summary": "х" * 141}), encoding="utf-8")
    assert hm.cmd_apply(args(node="rule:doc-rules", json=str(bad)), root, data) == 1


def run_json(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(*a)
    return code, json.loads(buf.getvalue())


def test_edges_collapse_per_pair_and_type(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "rules" / "doc-rules.mdc",
        "---\ndescription: rules\n---\n\n# One\n\nSee `.agents/skills/demo/SKILL.md`.\n\n# Two\n\nAlso `.agents/skills/demo/SKILL.md`.\n",
    )
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    edges = [e for e in graph["edges"] if e["source"] == "rule:doc-rules" and e["target"] == "skill:demo"]
    assert len(edges) == 1
    assert edges[0]["blocks"] == 2
    assert len(edges[0]["anchors"]) == 2
    assert graph["stats"]["relation_blocks"] >= graph["stats"]["edges"]


def test_get_slim_omits_blocks(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_get, args(node="skill:demo", slim=True), root, data)
    assert code == 0
    assert "content_blocks" not in payload["node"]
    assert payload["node"]["summary"]
    assert payload["node"]["path"].endswith("demo/SKILL.md")
    assert isinstance(payload["edges"]["incoming"], list)


def test_bundle_lists_skill_files_and_edges(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "skills" / "demo" / "references" / "notes.md", "# Notes\n\nSee `../SKILL.md`.\n")
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_bundle, args(skill="demo"), root, data)
    assert code == 0
    assert payload["main"] == "skill:demo"
    assert len(payload["files"]) == 2
    assert payload["edges"]["outgoing"]
    assert any(item["id"] == "rule:doc-rules" for item in payload["edges"]["outgoing"])


def test_bundle_finds_nested_child_skill(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "skills" / "parent" / "children" / "child" / "SKILL.md",
        "---\nname: child\ndescription: child skill\n---\n\n# Child\n\nRun `.cursor/rules/doc-rules.mdc`.\n",
    )
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_bundle, args(skill="child"), root, data)
    assert code == 0
    assert payload["main"] == "skill:child"
    assert len(payload["files"]) == 1


def test_audit_reports_warnings_and_verdict(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_audit, args(skill="demo"), root, data)
    assert code == 0
    assert payload["verdict"] == "review"
    assert payload["files"]
    assert any("смысловой анализ" in w for w in payload["warnings"])

    code, payload = run_json(hm.cmd_audit, args(node="skill:demo"), root, data)
    assert code == 0
    assert payload["target"]["node"] == "skill:demo"

    assert hm.cmd_audit(args(), root, data) == 2


def test_lint_detects_self_cycle_and_missing_trigger(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "skills" / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: demo skill\n---\n\n# Demo\n\nRun `.agents/skills/demo/SKILL.md` again.\n",
    )
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, report = run_json(hm.cmd_lint, args(), root, data)
    assert code == 0
    kinds = {(i["kind"], i["node"]) for i in report["issues"]}
    assert ("self_relation", "skill:demo") not in kinds
    assert ("no_trigger", "skill:demo") in kinds

    node_file = data / "nodes" / "skill__demo.json"
    node = json.loads(node_file.read_text(encoding="utf-8"))
    node["content_blocks"][-1]["relations"].append({
        "target_name": "demo", "target_type": "skill",
        "target_path": ".agents/skills/demo/SKILL.md", "target_node_id": "skill:demo",
        "relation_type": "delegates_to", "origin": "agent", "resolution": "resolved",
        "anchor_text": "Demo", "execution_moment": "",
    })
    node_file.write_text(json.dumps(node), encoding="utf-8")
    hm.cmd_build(args(), root, data)
    code, report = run_json(hm.cmd_lint, args(), root, data)
    kinds = {(i["kind"], i["node"]) for i in report["issues"]}
    assert ("self_relation", "skill:demo") in kinds
    assert report["by_severity"]["warn"] >= 1


def test_review_skill_returns_outline_and_questions(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_review, args(skill="demo", all=False), root, data)
    assert code == 0
    assert payload["files"]
    headers = [row["header"] for row in payload["files"][0]["outline"]]
    assert any("Demo" in h for h in headers)
    assert payload["questions"]
    assert "edges" in payload


def test_review_all_lists_canon_skills_and_rules(tmp_path):
    root = make_repo(tmp_path)
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    code, payload = run_json(hm.cmd_review, args(all=True), root, data)
    assert code == 0
    ids = {item["node"] for item in payload["items"]}
    assert "skill:demo" in ids
    assert "rule:doc-rules" in ids
    item = next(i for i in payload["items"] if i["node"] == "skill:demo")
    assert "summary" in item and "issues" in item


if __name__ == "__main__":
    sys.exit("run with pytest")


def test_set_block_recompiles_and_keeps_history(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    block = next(b for b in node["content_blocks"] if b["header_text"] == "Rules")
    result = hm.set_block(root, data, "rule:doc-rules", block["block_id"], "# Rules\n\nEdited body.\n")
    assert result["status"] == "ok"
    source = (root / ".cursor" / "rules" / "doc-rules.mdc").read_text(encoding="utf-8")
    assert "Edited body." in source
    assert source.count("# Rules") == 1
    assert list((data / "nodes" / ".history").glob("*.json"))
    assert hm.cmd_check(args(), root, data) == 0


def test_set_block_refuses_mirror(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    try:
        hm.set_block(root, data, "skill:demo@antigravity", "b000", "# x\n")
    except hm.MirrorError as exc:
        assert exc.code == 1
    else:
        raise AssertionError("mirror write must fail")


def test_graph_logical_ids_dedupe(tmp_path):
    root = make_repo(tmp_path)
    scan(root, include_mirrors=True)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    assert graph["stats"]["logical"] == graph["stats"]["canonical"]
    mirror = next(n for n in graph["nodes"] if not n["canonical"])
    assert mirror["logical_id"] == mirror["projection_of"]
    assert any(e["type"] == "mirrors" for e in graph["edges"])


def test_relative_links_resolve_from_source(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "skills" / "demo" / "references" / "notes.md",
        "# Notes\n\nSee [other](../SKILL.md) and [rules](../../../rules/doc-rules.mdc).\n",
    )
    scan(root)
    data = data_of(root)
    node = json.loads((data / "nodes" / "doc__demo-notes.json").read_text(encoding="utf-8"))
    targets = {r["target_node_id"] for b in node["content_blocks"] for r in b["relations"] if r["resolution"] == "resolved"}
    assert "skill:demo" in targets
    assert "rule:doc-rules" in targets


def test_canon_edges_are_present(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "skills" / "demo" / "references" / "notes.md",
        "# Notes\n\nSee [other](../SKILL.md).\n",
    )
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    canon = {n["id"] for n in graph["nodes"] if n["canonical"]}
    edges = [e for e in graph["edges"] if e["source"] in canon and e["target"] in canon and e["type"] != "mirrors"]
    assert edges, "canonical graph must contain relations"


def test_mcp_servers_become_nodes(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "mcp.json",
        json.dumps({"mcpServers": {"demo-mcp": {"command": "npx", "args": ["-y", "demo"]}}}),
    )
    write(
        root / ".cursor" / "rules" / "doc-rules.mdc",
        "---\ndescription: rules\n---\n\n# Rules\n\nUse demo-mcp for the graph.\n",
    )
    scan(root)
    data = data_of(root)
    hm.cmd_build(args(), root, data)
    graph = json.loads((data / "graph.json").read_text(encoding="utf-8"))
    servers = [n for n in graph["nodes"] if n["type"] == "mcp"]
    assert [n["id"] for n in servers] == ["mcp:demo-mcp"]
    assert graph["stats"]["mcp"] == 1
    edges = [e for e in graph["edges"] if e["target"] == "mcp:demo-mcp"]
    assert edges and edges[0]["type"] == "invokes_tool"
    assert hm.cmd_check(args(), root, data) == 0


def test_mcp_config_values_are_not_stored(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "mcp.json",
        json.dumps({"mcpServers": {"demo-mcp": {"command": "npx", "env": {"DEMO_TOKEN": "super-secret-value"}}}}),
    )
    _rel, servers = hm.load_mcp_servers(root)
    assert list(servers) == ["demo-mcp"]
    assert servers["demo-mcp"]["env_keys"] == ["DEMO_TOKEN"]
    assert "super-secret-value" not in json.dumps(servers)


def test_mcp_mention_needs_context(tmp_path):
    root = make_repo(tmp_path)
    write(
        root / ".cursor" / "mcp.json",
        json.dumps({"mcpServers": {
            "git": {"command": "uvx", "args": ["mcp-server-git"]},
            "serena": {"command": "uvx", "args": ["serena"]},
            "demo-mcp": {"command": "npx", "args": ["demo"]},
        }}),
    )
    write(
        root / ".cursor" / "rules" / "doc-rules.mdc",
        "---\ndescription: rules\n---\n\n# Rules\n\nRun `git status` and `mysql -e 'select 1'`.\n\n"
        "MCP Gate: demo-mcp then serena.\n\nUse demo-mcp directly.\n",
    )
    scan(root)
    data = data_of(root)
    node = json.loads((data / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    targets = {r["target_node_id"] for b in node["content_blocks"] for r in b.get("relations", []) if r["target_type"] == "mcp"}
    assert "mcp:git" not in targets
    assert "mcp:demo-mcp" in targets
    assert "mcp:serena" in targets


def test_mcp_file_names_are_not_server_mentions(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "mcp.json", json.dumps({"mcpServers": {"git": {"command": "uvx"}}}))
    write(
        root / ".cursor" / "rules" / "doc-rules.mdc",
        "---\ndescription: rules\n---\n\n# Rules\n\nRun `git check-ignore -v .cursor/mcp.json`.\n\nSecrets live in mcp.env, not in git.\n",
    )
    scan(root)
    node = json.loads((data_of(root) / "nodes" / "rule__doc-rules.json").read_text(encoding="utf-8"))
    assert not [r for b in node["content_blocks"] for r in b.get("relations", []) if r["target_type"] == "mcp"]


def test_bare_name_resolves_inside_skill(tmp_path):
    root = make_repo(tmp_path)
    write(root / ".cursor" / "skills" / "demo" / "references" / "notes.md", "# Notes\n\nSee `README.md`.\n")
    write(root / ".cursor" / "skills" / "demo" / "README.md", "# Demo readme\n")
    write(root / ".cursor" / "skills" / "other" / "SKILL.md", "---\nname: other\ndescription: o\n---\n\n# Other\n")
    write(root / ".cursor" / "skills" / "other" / "README.md", "# Other readme\n")
    scan(root)
    node = json.loads((data_of(root) / "nodes" / "doc__demo-notes.json").read_text(encoding="utf-8"))
    ids = {r.get("target_node_id") for b in node["content_blocks"] for r in b.get("relations", [])}
    assert "doc:demo-readme" in ids
