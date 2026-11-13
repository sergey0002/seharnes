#!/usr/bin/env python3
"""Regression tests for the agent-view sync toolchain.

Covers the checks the sync relies on: tree and rule parity, manifest freshness,
MCP view invariants, and stale artifact cleanup in the generators.

Run: python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
Exit code 0 when every case passes, 1 otherwise.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
SCRIPTS = HERE.parent / "scripts"
PARITY_DIR = ROOT / ".cursor" / "scripts" / "harness"
MCP_DIR = ROOT / ".agents" / "skills" / "harness-router" / "children" / "mcp-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(PARITY_DIR))

import rule_model
import verify_mcp_views as mcp  # noqa: E402
import verify_parity as parity  # noqa: E402


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_agent_configs", SCRIPTS / "generate-agent-configs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mcp_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_mcp_config", SCRIPTS / "generate-mcp-config.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_qoder_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_qoder_config", SCRIPTS / "generate-qoder-config.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_qwen_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_qwen_config", SCRIPTS / "generate-qwen-config.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_antigravity_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_antigravity_rules", SCRIPTS / "generate-antigravity-rules.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rule_model_classification() -> None:
    assert rule_model.classify({"alwaysApply": "true", "globs": ["**.php"]}) == rule_model.ALWAYS
    block = rule_model.parse_frontmatter(
        "---\ndescription: x\nglobs:\n  - '**.php'\n  - '**.tpl'\nalwaysApply: false\n---\n\n# X\n"
    )
    assert rule_model.classify(block) == rule_model.CONDITIONAL
    assert rule_model.rule_paths(block) == ["**.php", "**.tpl"]
    assert rule_model.visibility_contract("kilo", {"gate": "true"}) == "inline"
    assert rule_model.visibility_contract("kilo", {"attach": "glob"}) == "generated-glob-block"
    assert rule_model.visibility_contract("qoder", {"attach": "glob"}) == "glob"
    inline = rule_model.parse_frontmatter(
        '---\ndescription: x\nglobs: ["**.php"]\nalwaysApply: false\n---\n\n# X\n'
    )
    assert rule_model.rule_paths(inline) == ["**.php"]
    assert rule_model.classify({"description": "x"}) == rule_model.AGENT_REQUESTED
    assert rule_model.classify({}) == rule_model.MANUAL
    assert rule_model.body_without_frontmatter("---\na: b\n---\n\n# Body\n") == "# Body\n"


def test_antigravity_block_globs() -> None:
    generator = load_antigravity_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / ".cursor" / "rules"
        rules.mkdir(parents=True)
        (rules / "doc-verify.mdc").write_text(
            "---\ndescription: verify docs\nglobs:\n  - '**.php'\n  - '**.tpl'\nalwaysApply: false\n---\n\n# Verify\n",
            encoding="utf-8",
        )
        (rules / "always.mdc").write_text(
            "---\ndescription: always rule\nalwaysApply: true\n---\n\n# Always\n",
            encoding="utf-8",
        )

        assert generator.main(["--root", str(root)]) == 0

        verify = (root / ".agents" / "rules" / "doc-verify.md").read_text(encoding="utf-8")
        assert "trigger: glob" in verify, verify
        assert 'globs: "**.php, **.tpl"' in verify, verify
        always = (root / ".agents" / "rules" / "always.md").read_text(encoding="utf-8")
        assert "trigger: always_on" in always, always
        extra = root / ".agents" / "rules" / "nested" / "always.md"
        extra.parent.mkdir()
        extra.write_text("local\n", encoding="utf-8")
        assert generator.main(["--root", str(root), "--check"]) == 1
        assert generator.main(["--root", str(root)]) == 0
        assert not extra.exists()
        assert generator.main(["--root", str(root), "--check"]) == 0


def test_native_discovery_contract() -> None:
    generator = load_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / ".cursor/rules"
        rules.mkdir(parents=True)
        (rules / "gates.mdc").write_text("---\nalwaysApply: true\ngate: true\n---\n# Guard\n", encoding="utf-8")
        skill = root / ".agents/skills/router/children/child/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: child\ndescription: child workflow\n---\n# Canon\n', encoding="utf-8")
        (root / "AGENTS.md").write_text("# Local instructions\n", encoding="utf-8")
        config = root / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text('model_instructions_file = "AGENTS.md"\napproval_policy = "on-request"\n', encoding="utf-8")
        legacy = root / ".codex/skills/unique/SKILL.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("local work", encoding="utf-8")
        generator.sync_discovery(root)
        generator.generate_codex(root)
        text = (root / "AGENTS.md").read_text(encoding="utf-8")
        assert "# Guard" in text and "# Local instructions" in text
        assert "model_instructions_file" not in config.read_text(encoding="utf-8")
        assert "approval_policy" in config.read_text(encoding="utf-8")
        assert not (root / ".codex/skills").exists()
        assert list((root / ".doc/skil_data/environment-sync/backups").rglob("SKILL.md"))
        manifest = json.loads((root / ".agents/skills.json").read_text(encoding="utf-8"))
        assert manifest["entries"] == [{"path": ".agents/skills/router/children/child"}]
        assert "router/children/child/SKILL.md" in (root / ".dsh/skills/child/SKILL.md").read_text(encoding="utf-8")
        assert generator.sync_discovery(root, check=True) == []
        generator.sync_discovery(root)
        generator.generate_codex(root)
        assert (root / "AGENTS.md").read_text(encoding="utf-8") == text
        wrapper = root / ".dsh/skills/child/SKILL.md"
        wrapper.write_text("user edit", encoding="utf-8")
        assert generator.sync_discovery(root, check=True)
        try:
            generator.sync_discovery(root)
        except ValueError:
            pass
        else:
            raise AssertionError("unmanaged discovery edit overwritten")


def test_relocated_links() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / ".cursor/rules/a.mdc"
        source.parent.mkdir(parents=True)
        resource = source.with_name("b.mdc")
        resource.write_text("# B\n", encoding="utf-8")
        target = root / ".agents/rules/a.md"
        body = "[B](b.mdc#anchor) [web](https://example.org) [section](#here)"
        relocated = rule_model.rebase_links(body, source, target)
        assert "../../.cursor/rules/b.mdc#anchor" in relocated
        source.write_text("---\ndescription: a\n---\n" + body, encoding="utf-8")
        target.parent.mkdir(parents=True)
        target.write_text(relocated, encoding="utf-8")
        assert parity.compare_rules(source.parent, target.parent, allow_extra=True) == [f"{target.parent}: rules missing b"]


def test_tree_parity() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canon, view = root / "canon", root / "view"
        (canon / "a").mkdir(parents=True)
        (view / "a").mkdir(parents=True)
        (canon / "a" / "s.md").write_text("body\n", encoding="utf-8")

        (view / "a" / "s.md").write_text("body\r\n", encoding="utf-8")
        assert parity.compare(canon, view) == [], "line endings must not count as drift"

        (view / "a" / "s.md").write_text("other\n", encoding="utf-8")
        assert any("mismatch a/s.md" in item for item in parity.compare(canon, view))

        (view / "a" / "extra.txt").write_text("x", encoding="utf-8")
        assert any("extra a/extra.txt" in item for item in parity.compare(canon, view))

        (view / "a" / "s.md").unlink()
        assert any("missing a/s.md" in item for item in parity.compare(canon, view))


def test_rules_body_parity() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canon, view = root / "canon", root / "view"
        canon.mkdir()
        view.mkdir()
        (canon / "a.mdc").write_text(
            "---\ndescription: x\nalwaysApply: true\n---\n\n# Rule A\n",
            encoding="utf-8",
        )
        (view / "a.md").write_text("# Rule A\n", encoding="utf-8")
        assert parity.compare_rules(canon, view) == [], "frontmatter must be stripped"

        (view / "a.md").write_text("# Rule B\n", encoding="utf-8")
        assert any("rules mismatch a" in item for item in parity.compare_rules(canon, view))

        (view / "orphan.md").write_text("# x\n", encoding="utf-8")
        assert any("rules extra orphan" in item for item in parity.compare_rules(canon, view))

        (canon / "b.mdc").write_text("# b\n", encoding="utf-8")
        assert any("rules missing b" in item for item in parity.compare_rules(canon, view))


def test_manifest_freshness() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canon = root / "skills"
        canon.mkdir()
        (canon / "a.md").write_text("body\n", encoding="utf-8")
        report_path = root / "report.json"

        assert parity.check_freshness(report_path, canon)

        report = {"status": "passed", "canon_hash": parity.canon_hash(canon)}
        report_path.write_text(json.dumps(report), encoding="utf-8")
        assert parity.check_freshness(report_path, canon) == []

        (canon / "a.md").write_text("changed\n", encoding="utf-8")
        stale = parity.check_freshness(report_path, canon)
        assert any("stale" in item for item in stale), stale

        report["canon_hash"] = parity.canon_hash(canon)
        report["status"] = "failed"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        assert any("status" in item for item in parity.check_freshness(report_path, canon))


def test_mcp_view_invariants() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canonical = root / "mcp.json"
        canonical.write_text(json.dumps({"mcpServers": {
            "one": {"command": "npx", "args": ["a"]},
            "two": {"command": "npx", "args": ["b"], "disabled": True},
        }}), encoding="utf-8")

        kilo = root / "kilo.jsonc"
        kilo.write_text(
            "// generated\n"
            + json.dumps({"mcp": {"one": {"type": "local", "command": ["npx"]},
                                  "two": {"type": "local", "command": ["npx"], "enabled": False}}}),
            encoding="utf-8",
        )
        errors: list[str] = []
        canon = mcp.canon_servers(canonical, errors)
        mcp.check_kilo(canon, kilo, errors)
        assert errors == [], errors

        kilo.write_text(
            "// generated\n"
            + json.dumps({"mcp": {"one": {"type": "local", "command": ["npx"], "enabled": False},
                                  "two": {"type": "local", "command": ["npx"], "enabled": False}}}),
            encoding="utf-8",
        )
        errors = []
        mcp.check_kilo(canon, kilo, errors)
        assert any("enabled=" in item for item in errors), errors

        expanded = root / "expanded.json"
        expanded.write_text(json.dumps({"mcpServers": {
            "one": {"command": "npx", "args": ["${env:TOKEN}"]},
        }}), encoding="utf-8")
        errors = []
        mcp.check_expanded(canon, expanded, errors)
        assert any("unresolved placeholder" in item for item in errors), errors
        assert any("server missing two" in item for item in errors), errors

        codex = root / "config.toml"
        codex.write_text('[mcp_servers."one"]\ncommand = "npx"\n[mcp_servers."two"]\nenabled = false\n', encoding="utf-8")
        errors = []
        mcp.check_codex_toml(canon, codex, errors)
        assert errors == [], errors
        codex.write_text('[mcp_servers."one"]\nenabled = false\n[mcp_servers."two"]\nenabled = false\n', encoding="utf-8")
        errors = []
        mcp.check_codex_toml(canon, codex, errors)
        assert any("enabled=" in item for item in errors), errors


def test_windows_global_config_replaced() -> None:
    script = (SCRIPTS / "sync-agent-views.sh").read_text(encoding="utf-8")
    block = script.split('if [ -n "$WIN_HOME" ] && [ -d "$WIN_HOME/.gemini/config" ]; then', 1)[1]
    block = 'if [ -n "$WIN_HOME" ] && [ -d "$WIN_HOME/.gemini/config" ]; then' + block.split('\necho "--- Generating DeepSeek', 1)[0]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / ".gemini" / "config" / "mcp_config.json"
        target.parent.mkdir(parents=True)
        artifact = root / "generated.json"
        artifact.write_text('{"generated": true}\n', encoding="utf-8")
        target.write_text('{"foreign": true}\n', encoding="utf-8")
        result = subprocess.run(["bash", "-euc", block, "test", str(root), str(artifact)],
                                env={"WIN_HOME": str(root), "WINDOWS_WSL_ARTIFACT": str(artifact)},
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert target.read_bytes() == artifact.read_bytes()
        result = subprocess.run(["bash", "-euc", block],
                                env={"WIN_HOME": str(root), "WINDOWS_WSL_ARTIFACT": str(artifact)},
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert target.read_bytes() == artifact.read_bytes()


def test_generator_stale_cleanup() -> None:
    generator = load_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".cursor" / "rules").mkdir(parents=True)
        (root / ".cursor" / "scripts").mkdir()
        (root / ".agents" / "skills").mkdir(parents=True)
        (root / "AGENTS.md").write_text("# Canonical instructions\n", encoding="utf-8")
        (root / ".cursor" / "rules" / "a.mdc").write_text(
            "---\ndescription: x\n---\n\n# A\n", encoding="utf-8"
        )
        codex = root / ".codex"
        (codex / "skills" / "old").mkdir(parents=True)
        (codex / "skills" / "old" / "SKILL.md").write_text("stale\n", encoding="utf-8")
        (codex / "mcp.json").write_text("{}", encoding="utf-8")
        (codex / "mcp.env").write_text("OLD=1\n", encoding="utf-8")

        generator.generate_codex(root)

        assert (codex / "mcp.json").exists(), "local mcp.json must be kept"
        assert (codex / "mcp.env").exists(), "local mcp.env must be kept"
        assert not (codex / "skills" / "old").exists(), "extra skill must be removed"
        assert (codex / "rules" / "a.md").exists(), "rule mirror must be generated"
        assert "Canonical instructions" in (root / "AGENTS.md").read_text(encoding="utf-8")
        assert "rules-index.md" in (root / "AGENTS.md").read_text(encoding="utf-8")
        assert not (codex / "skills").exists()
        extra = codex / "rules" / "old.md"
        extra.write_text("old\n", encoding="utf-8")
        generator.generate_codex(root)
        assert not extra.exists()


def test_kilo_fragment_lifecycle() -> None:
    generator = load_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".cursor" / "rules").mkdir(parents=True)
        (root / ".cursor" / "scripts").mkdir()
        canonical = root / ".cursor" / "mcp.json"
        canonical.write_text(json.dumps({"mcpServers": {
            "one": {"command": "npx", "args": ["a"], "alwaysAllow": ["tool"]},
        }}), encoding="utf-8")

        generator.generate_kilo(root)
        fragment = root / ".kilo" / "kilo-permissions.fragment.jsonc"
        assert fragment.exists(), "fragment must be written when permissions exist"
        text = fragment.read_text(encoding="utf-8")
        assert "one_tool" in text and "allow" in text

        canonical.write_text(json.dumps({"mcpServers": {
            "one": {"command": "npx", "args": ["a"]},
        }}), encoding="utf-8")
        generator.generate_kilo(root)
        assert not fragment.exists(), "stale generated fragment must be removed"


def test_kilo_rule_selection() -> None:
    generator = load_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / ".cursor" / "rules"
        (rules / "mcp").mkdir(parents=True)
        (root / ".cursor" / "scripts").mkdir()
        (rules / "always.mdc").write_text(
            "---\ndescription: always rule\nalwaysApply: true\n---\n\n# Always\n",
            encoding="utf-8",
        )
        (rules / "model.mdc").write_text(
            "---\ndescription: model rule\nalwaysApply: false\n---\n\n# Model\n",
            encoding="utf-8",
        )
        (rules / "globbed.mdc").write_text(
            "---\ndescription: glob rule\nglobs:\n  - '**.php'\n  - '**.tpl'\nalwaysApply: false\n---\n\n# Globbed\n",
            encoding="utf-8",
        )
        (rules / "manual.mdc").write_text("# Manual\n", encoding="utf-8")
        (rules / "mcp" / "nested.mdc").write_text(
            "---\ndescription: nested\nalwaysApply: true\n---\n\n# Nested\n",
            encoding="utf-8",
        )
        (root / ".cursor" / "mcp.json").write_text(
            json.dumps({"mcpServers": {}}), encoding="utf-8"
        )

        generator.generate_kilo(root)

        text = (root / ".kilo" / "kilo.jsonc").read_text(encoding="utf-8")
        payload = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("//")
        )
        instructions = json.loads(payload)["instructions"]

        assert ".kilo/rules/always.md" in instructions
        assert ".kilo/rules/mcp/nested.md" in instructions
        assert ".kilo/rules/model.md" not in instructions
        assert ".kilo/rules/globbed.md" not in instructions
        assert ".kilo/rules/manual.md" not in instructions
        assert ".kilo/rules-index.md" in instructions

        index = (root / ".kilo" / "rules-index.md").read_text(encoding="utf-8")
        assert "model.md" in index and "globbed.md" in index and "manual.md" in index
        assert "**.php" in index and "**.tpl" in index
        assert "<!-- glob-triggers -->" in index
        assert "| `**.php` | `globbed` | `.kilo/rules/globbed.md` |" in index
        assert "always.md" not in index and "nested.md" not in index


def test_windows_wsl_render() -> None:
    generator = load_mcp_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".cursor").mkdir(parents=True)
        (root / ".cursor" / "mcp.env").write_text(
            "SECRET_TOKEN=hidden\n", encoding="utf-8"
        )
        (root / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
            "remote": {"type": "http", "url": "http://127.0.0.1:9131/mcp"},
            "local": {
                "type": "stdio",
                "command": "bash",
                "args": ["${workspaceFolder}/run.sh"],
                "envFile": "${workspaceFolder}/.cursor/mcp.env",
                "env": {"LITERAL": "x"},
            },
            "off": {"command": "npx", "args": ["x"], "disabled": True},
            "codeprism": {"command": "npx", "args": ["x"], "enabled": False},
            "remote-off": {"type": "http", "url": "http://127.0.0.1:1/mcp", "enabled": False},
            "xdebug": {"command": "npx", "enabled": False},
        }}), encoding="utf-8")
        out = root / "windows.json"

        assert generator.main([
            str(root), "--host", "windows-wsl", "--distro", "Ubuntu", "--out", str(out)
        ]) == 0

        text = out.read_text(encoding="utf-8")
        servers = json.loads(text)["mcpServers"]
        assert servers["remote"]["serverUrl"] == "http://127.0.0.1:9131/mcp"
        local = servers["local"]
        assert local["command"] == "wsl.exe", local
        assert local["args"][:3] == ["-d", "Ubuntu", "--"], local
        script = local["args"][-1]
        assert "cd " in script
        assert ". " in script and "mcp.env" in script
        assert "export LITERAL=x" in script
        assert f"exec bash {root}/run.sh" in script, script
        assert servers["off"]["disabled"] is True
        assert servers["codeprism"]["disabled"] is True
        assert servers["remote-off"]["disabled"] is True
        assert servers["remote"]["disabled"] is False
        assert servers["local"]["disabled"] is False
        assert "XDEBUG_PORT" not in servers["xdebug"]["args"][-1]
        errors = []
        canon = mcp.canon_servers(root / ".cursor" / "mcp.json", errors)
        mcp.check_expanded(canon, out, errors)
        assert not errors, errors
        servers["codeprism"]["disabled"] = False
        out.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
        mcp.check_expanded(canon, out, errors)
        assert any("codeprism enabled=True" in error for error in errors), errors
        assert "SECRET_TOKEN" not in text, "secrets must stay in the WSL env file"
        assert "${workspaceFolder}" not in text
        assert "${env:" not in text


def test_qoder_rules_and_skills() -> None:
    generator = load_qoder_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / ".cursor" / "rules"
        (rules / "mcp").mkdir(parents=True)
        (rules / "always.mdc").write_text(
            "---\ndescription: always rule\nalwaysApply: true\n---\n\n# Always\n",
            encoding="utf-8",
        )
        (rules / "globbed.mdc").write_text(
            "---\ndescription: glob rule\nglobs:\n  - '**.php'\n  - '**.tpl'\nalwaysApply: false\n---\n\n# Globbed\n",
            encoding="utf-8",
        )
        (rules / "model.mdc").write_text(
            "---\ndescription: model rule\nalwaysApply: false\n---\n\n# Model\n",
            encoding="utf-8",
        )
        (rules / "manual.mdc").write_text("# Manual\n", encoding="utf-8")
        (rules / "mcp" / "nested.mdc").write_text(
            "---\ndescription: nested\nalwaysApply: true\n---\n\n# Nested\n",
            encoding="utf-8",
        )
        (root / ".cursor" / "mcp.json").write_text(
            json.dumps({"mcpServers": {"one": {"command": "npx", "args": ["a"]}}}),
            encoding="utf-8",
        )
        skill = root / ".agents" / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\n\n# Demo\n", encoding="utf-8")
        (skill / ".data").mkdir()
        (skill / ".data" / "cache.json").write_text("{}", encoding="utf-8")

        assert generator.main(["--root", str(root)]) == 0

        assert "trigger: always_on" in (root / ".qoder" / "rules" / "always.md").read_text(encoding="utf-8")
        globbed = (root / ".qoder" / "rules" / "globbed.md").read_text(encoding="utf-8")
        assert "trigger: glob" in globbed and '"**.php"' in globbed, globbed
        assert "trigger: model_decision" in (root / ".qoder" / "rules" / "model.md").read_text(encoding="utf-8")
        assert "trigger: manual" in (root / ".qoder" / "rules" / "manual.md").read_text(encoding="utf-8")
        assert (root / ".qoder" / "rules" / "mcp-nested.md").exists()
        assert (root / ".qoder" / "skills" / "demo" / "SKILL.md").exists()
        assert not (root / ".qoder" / "skills" / "demo" / ".data").exists()
        assert generator.main(["--root", str(root), "--check"]) == 0

        (root / ".qoder" / "rules" / "local.md").write_text("# Local\n", encoding="utf-8")
        assert generator.main(["--root", str(root), "--check"]) == 1
        assert generator.main(["--root", str(root)]) == 3
        assert (root / ".qoder" / "rules" / "local.md").read_text(encoding="utf-8") == "# Local\n"
        (root / ".qoder" / "rules" / "local.md").unlink()
        assert generator.main(["--root", str(root)]) == 0
        assert not (root / ".qoder" / "rules" / "local.md").exists()
        managed = root / ".qoder" / "rules" / "always.md"
        managed.write_text("local edit\n", encoding="utf-8")
        assert generator.main(["--root", str(root), "--preflight"]) == 0
        assert managed.read_text(encoding="utf-8") == "local edit\n"
        assert generator.main(["--root", str(root)]) == 0
        backups = list((root / ".doc/skil_data/environment-sync/backups/qoder-preflight").glob("*/rules/always.md"))
        assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == "local edit\n"
        assert "trigger: always_on" in managed.read_text(encoding="utf-8")


def test_qoder_mcp_render() -> None:
    generator = load_qoder_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cursor = root / ".cursor"
        (cursor / "scripts").mkdir(parents=True)
        (cursor / "rules").mkdir()
        (root / ".agents" / "skills").mkdir(parents=True)
        (cursor / "scripts" / "run-with-mcp-env.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        (cursor / "mcp.env").write_text("SECRET_TOKEN=hidden\n", encoding="utf-8")
        (cursor / "mcp.json").write_text(json.dumps({"mcpServers": {
            "remote": {"type": "http", "url": "http://127.0.0.1:9131/mcp",
                       "alwaysAllow": ["search"]},
            "local": {"type": "stdio", "command": "bash",
                      "args": ["${workspaceFolder}/run.sh"],
                      "envFile": "${workspaceFolder}/.cursor/mcp.env",
                      "env": {"LITERAL": "x", "TOKEN": "${env:SECRET_TOKEN}"}},
            "off": {"type": "stdio", "command": "npx", "args": ["x"], "disabled": True},
            "limited": {"type": "stdio", "command": "uvx", "args": ["y"],
                        "disabledTools": ["danger"], "includeTools": ["safe"]},
        }}), encoding="utf-8")

        assert generator.main(["--root", str(root)]) == 0
        settings = json.loads((root / ".qoder" / "settings.json").read_text(encoding="utf-8"))
        servers = settings["mcpServers"]

        assert servers["remote"]["type"] == "http"
        assert servers["remote"]["alwaysAllow"] == ["search"]
        local = servers["local"]
        assert local["type"] == "stdio"
        assert local["command"] == "bash"
        assert local["args"][0].endswith("run-with-mcp-env.sh"), local
        assert local["args"][1] == "bash"
        assert f"{root}/run.sh" in local["args"], local
        assert local["env"] == {"LITERAL": "x"}, local
        assert servers["off"]["disabled"] is True
        assert servers["limited"]["excludeTools"] == ["danger"]
        assert servers["limited"]["includeTools"] == ["safe"]
        assert settings["mcp"]["enabledProjectMcpServers"] == ["limited", "local", "remote"]
        text = (root / ".qoder" / "settings.json").read_text(encoding="utf-8")
        assert "SECRET_TOKEN" not in text, "secrets must stay in mcp.env"

        settings["mcpServers"]["target-only"] = {"type": "stdio", "command": "npx"}
        settings["mcp"]["enabledProjectMcpServers"].append("target-only")
        settings["mcp"]["custom"] = True
        settings["theme"] = "dark"
        (root / ".qoder" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (root / ".qoder" / "skills" / "local").mkdir(parents=True)
        (root / ".qoder" / "skills" / "local" / "SKILL.md").write_text("# Local\n", encoding="utf-8")

        assert generator.main(["--root", str(root), "--check"]) == 1
        assert generator.main(["--root", str(root)]) == 3
        assert generator.main(["--root", str(root), "--replace-managed-mcp"]) == 3
        assert (root / ".qoder" / "skills" / "local" / "SKILL.md").exists()
        assert "target-only" in json.loads((root / ".qoder" / "settings.json").read_text(encoding="utf-8"))["mcpServers"]
        (root / ".qoder" / "skills" / "local" / "SKILL.md").unlink()
        (root / ".qoder" / "skills" / "local").rmdir()
        settings = json.loads((root / ".qoder" / "settings.json").read_text(encoding="utf-8"))
        del settings["mcpServers"]["target-only"]
        settings["mcp"]["enabledProjectMcpServers"].remove("target-only")
        (root / ".qoder" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        assert generator.main(["--root", str(root)]) == 0
        merged = json.loads((root / ".qoder" / "settings.json").read_text(encoding="utf-8"))
        assert "target-only" not in merged["mcpServers"]
        assert "target-only" not in merged["mcp"]["enabledProjectMcpServers"]
        assert merged["mcp"]["custom"] is True and merged["theme"] == "dark"
        assert not (root / ".qoder" / "skills" / "local" / "SKILL.md").exists()
        assert generator.main(["--root", str(root), "--check"]) == 0


def test_sync_qoder_preflight_before_writes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        script_dir = root / ".agents/skills/harness-router/children/environment-sync/scripts"
        script_dir.mkdir(parents=True)
        for name in ("sync-agent-views.sh", "generate-qoder-config.py", "rule_model.py"):
            (script_dir / name).write_bytes((SCRIPTS / name).read_bytes())
        (root / ".cursor/rules").mkdir(parents=True)
        (root / ".cursor/mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
        canonical = root / ".agents/skills/demo/SKILL.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Demo\n", encoding="utf-8")
        local = root / ".qoder/skills/local/SKILL.md"
        local.parent.mkdir(parents=True)
        local.write_text("# Local\n", encoding="utf-8")
        result = subprocess.run(["bash", str(script_dir / "sync-agent-views.sh"), "--local-only"],
                                cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == 3, result.stdout + result.stderr
        assert local.read_text(encoding="utf-8") == "# Local\n"
        assert not (root / ".codex").exists()
        assert not (root / ".doc").exists()
        local.unlink()
        local.parent.rmdir()
        outside = root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("safe", encoding="utf-8")
        (root / ".qoder/skills/escape").symlink_to(outside, target_is_directory=True)
        result = subprocess.run(["bash", str(script_dir / "sync-agent-views.sh"), "--local-only"],
                                cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == 3, result.stdout + result.stderr
        assert (outside / "keep.txt").read_text(encoding="utf-8") == "safe"
        assert not (root / ".codex").exists()


def test_parity_allow_extra() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        canon, view = root / "canon", root / "view"
        canon.mkdir()
        view.mkdir()
        (canon / "a.md").write_text("body\n", encoding="utf-8")
        (view / "a.md").write_text("body\n", encoding="utf-8")
        (view / "local.md").write_text("local\n", encoding="utf-8")
        assert any("extra local.md" in item for item in parity.compare(canon, view))
        assert parity.compare(canon, view, allow_extra=True) == []

        canon_rules, view_rules = root / "cr", root / "vr"
        canon_rules.mkdir()
        view_rules.mkdir()
        (canon_rules / "a.mdc").write_text("---\ndescription: x\n---\n\n# A\n", encoding="utf-8")
        (view_rules / "a.md").write_text("# A\n", encoding="utf-8")
        (view_rules / "local.md").write_text("# Local\n", encoding="utf-8")
        assert any("rules extra local" in item for item in parity.compare_rules(canon_rules, view_rules))
        assert parity.compare_rules(canon_rules, view_rules, allow_extra=True) == []


def test_qwen_rules_and_mcp() -> None:
    generator = load_qwen_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / ".cursor" / "rules"
        (rules / "mcp").mkdir(parents=True)
        (rules / "always.mdc").write_text(
            "---\ndescription: always rule\nalwaysApply: true\n---\n\n# Always\n",
            encoding="utf-8",
        )
        (rules / "globbed.mdc").write_text(
            "---\ndescription: glob rule\nglobs:\n  - '**.php'\nalwaysApply: false\n---\n\n# Globbed\n",
            encoding="utf-8",
        )
        (rules / "model.mdc").write_text(
            "---\ndescription: model rule\nalwaysApply: false\n---\n\n# Model\n",
            encoding="utf-8",
        )
        (rules / "mcp" / "nested.mdc").write_text(
            "---\ndescription: nested\nalwaysApply: true\n---\n\n# Nested\n",
            encoding="utf-8",
        )
        (root / ".cursor" / "scripts").mkdir(parents=True)
        (root / ".cursor" / "scripts" / "run-with-mcp-env.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (root / ".cursor" / "mcp.env").write_text("SECRET_TOKEN=hidden\n", encoding="utf-8")
        (root / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {
            "local": {"type": "stdio", "command": "bash", "args": ["${workspaceFolder}/run.sh"],
                      "envFile": "${workspaceFolder}/.cursor/mcp.env",
                      "env": {"LITERAL": "x", "TOKEN": "${env:SECRET_TOKEN}"},
                      "alwaysAllow": ["read"]},
            "http": {"type": "http", "url": "http://127.0.0.1:9131/mcp"},
            "sse": {"type": "sse", "url": "http://127.0.0.1:7080/sse"},
            "off": {"type": "stdio", "command": "npx", "args": ["x"], "disabled": True},
        }}), encoding="utf-8")

        assert generator.main(["--root", str(root)]) == 0

        always = (root / ".qwen" / "rules" / "always.md").read_text(encoding="utf-8")
        assert "paths:" not in always and "trigger" not in always, always
        globbed = (root / ".qwen" / "rules" / "globbed.md").read_text(encoding="utf-8")
        assert "paths:" in globbed and '"**.php"' in globbed, globbed
        assert (root / ".qwen" / "rules" / "mcp-nested.md").exists()
        assert not (root / ".qwen" / "rules" / "model.md").exists()
        skill = (root / ".qwen" / "skills" / "rule-model" / "SKILL.md").read_text(encoding="utf-8")
        assert 'name: "rule-model"' in skill and "model rule" in skill, skill

        settings = json.loads((root / ".qwen" / "settings.json").read_text(encoding="utf-8"))
        servers = settings["mcpServers"]
        assert servers["http"]["httpUrl"] == "http://127.0.0.1:9131/mcp"
        assert servers["sse"]["url"] == "http://127.0.0.1:7080/sse"
        local = servers["local"]
        assert local["args"][0].endswith("run-with-mcp-env.sh"), local
        assert local["args"][1] == "bash" and f"{root}/run.sh" in local["args"]
        assert local["env"] == {"LITERAL": "x"} and local["trust"] is True
        assert "off" not in servers
        assert settings["mcp"]["excluded"] == ["off"]
        assert "SECRET_TOKEN" not in (root / ".qwen" / "settings.json").read_text(encoding="utf-8")
        assert generator.main(["--root", str(root), "--check"]) == 0

        servers["target-only"] = {"command": "npx"}
        settings["theme"] = "dark"
        (root / ".qwen" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (root / ".qwen" / "rules" / "local.md").write_text("# Local\n", encoding="utf-8")
        assert generator.main(["--root", str(root), "--check"]) == 1
        assert generator.main(["--root", str(root)]) == 0
        merged = json.loads((root / ".qwen" / "settings.json").read_text(encoding="utf-8"))
        assert "target-only" not in merged["mcpServers"]
        assert merged["theme"] == "dark"
        assert not (root / ".qwen" / "rules" / "local.md").exists()
        assert generator.main(["--root", str(root), "--check"]) == 0


def test_qwen_enabled_transition() -> None:
    generator = load_qwen_generator()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cursor = root / ".cursor"
        cursor.mkdir()
        (cursor / "rules").mkdir()
        canonical = cursor / "mcp.json"
        canonical.write_text(json.dumps({"mcpServers": {
            "codeprism": {"command": "npx", "enabled": False},
            "other": {"command": "npx", "disabled": True},
        }}), encoding="utf-8")
        assert generator.main(["--root", str(root)]) == 0
        settings_path = root / ".qwen" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        errors = []
        mcp.check_qwen(mcp.canon_servers(canonical, errors), settings_path, errors)
        assert not errors, errors
        settings["mcp"]["excluded"].append("local-only")
        settings["mcp"]["custom"] = True
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        canonical.write_text(json.dumps({"mcpServers": {
            "codeprism": {"command": "npx", "enabled": True},
            "other": {"command": "npx", "disabled": True},
        }}), encoding="utf-8")
        generated = generator.render_mcp(root)
        stale = generator.merge_settings(settings, generated)
        stale["mcp"]["excluded"].append("codeprism")
        settings_path.write_text(json.dumps(stale), encoding="utf-8")
        assert generator.main(["--root", str(root), "--check"]) == 1
        errors = []
        mcp.check_qwen(mcp.canon_servers(canonical, errors), settings_path, errors)
        assert any("enabled server codeprism" in error for error in errors), errors
        assert generator.main(["--root", str(root)]) == 0
        result = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "codeprism" in result["mcpServers"]
        assert result["mcp"]["excluded"] == ["other"]
        assert result["mcp"]["custom"] is True
        assert generator.main(["--root", str(root), "--check"]) == 0
        assert generator.main(["--root", str(root)]) == 0
        assert json.loads(settings_path.read_text(encoding="utf-8")) == result
        errors = []
        mcp.check_qwen(mcp.canon_servers(canonical, errors), settings_path, errors)
        assert not errors, errors
        assert generator.merge_settings({"mcp": {"excluded": ["codeprism"]}}, {
            "mcpServers": {"codeprism": {"command": "npx"}}
        }).get("mcp") is None


def test_missing_canon_preserves_mirrors() -> None:
    for load, adapter in ((load_qoder_generator, ".qoder"), (load_qwen_generator, ".qwen")):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".cursor").mkdir()
            (root / ".cursor" / "mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
            target = root / adapter / "rules" / "existing.md"
            target.parent.mkdir(parents=True)
            target.write_text("preserve", encoding="utf-8")
            assert load().main(["--root", str(root)]) == 2
            assert target.read_text(encoding="utf-8") == "preserve"


def test_qoder_qwen_strict_mirror_transitions() -> None:
    for client, generator in (("qoder", load_qoder_generator()), ("qwen", load_qwen_generator())):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rules = root / ".cursor" / "rules"
            rules.mkdir(parents=True)
            rule = rules / "dynamic.mdc"
            rule.write_text("---\ndescription: dynamic\nalwaysApply: false\n---\n\n# Rule\n", encoding="utf-8")
            canonical = root / ".cursor" / "mcp.json"
            canonical.write_text(json.dumps({"mcpServers": {
                "active": {"command": "one"}, "off": {"command": "two", "disabled": True}
            }}), encoding="utf-8")
            skill = root / ".agents" / "skills" / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# Demo\n", encoding="utf-8")
            assert generator.main(["--root", str(root)]) == 0
            view = root / ("." + client)
            settings_path = view / "settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["mcp"]["custom"] = {"keep": True}
            settings["editor"] = {"keep": True}
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            assert generator.main(["--root", str(root), "--check"]) == 0

            extra_rule = view / "rules" / "nested" / "extra.md"
            extra_rule.parent.mkdir(parents=True)
            extra_rule.write_text("extra", encoding="utf-8")
            assert generator.main(["--root", str(root), "--check"]) == 1
            extra_rule.unlink()

            extra_skill = view / "skills" / ("demo" if client == "qoder" else "rule-dynamic") / ".extra"
            extra_skill.write_text("extra", encoding="utf-8")
            assert generator.main(["--root", str(root), "--check"]) == 1
            extra_skill.unlink()
            if client == "qwen":
                local = view / "skills" / "local" / "SKILL.md"
                local.parent.mkdir(parents=True)
                local.write_text("# Local", encoding="utf-8")

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["mcp"]["enabledProjectMcpServers" if client == "qoder" else "excluded"].append("extra")
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            assert generator.main(["--root", str(root), "--check"]) == 1
            rule.write_text("---\nalwaysApply: true\n---\n\n# Changed\n", encoding="utf-8")
            skill.unlink()
            canonical.write_text(json.dumps({"mcpServers": {
                "active": {"command": "one", "disabled": True}, "off": {"command": "two"}
            }}), encoding="utf-8")
            if client == "qoder":
                assert generator.main(["--root", str(root)]) == 3
                assert (view / "skills" / "demo" / "SKILL.md").exists()
                (view / "skills" / "demo" / "SKILL.md").unlink()
                (view / "skills" / "demo").rmdir()
                extra_rule.parent.rmdir()
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                settings["mcp"]["enabledProjectMcpServers"].remove("extra")
                settings_path.write_text(json.dumps(settings), encoding="utf-8")
                before = settings_path.read_bytes()
                assert generator.main(["--root", str(root)]) == 3
                assert settings_path.read_bytes() == before
                assert generator.main(["--root", str(root), "--replace-managed-mcp"]) == 0
                backups = list((root / ".doc/skil_data/environment-sync/backups/qoder-preflight").glob("*/settings.json"))
                assert len(backups) == 1 and backups[0].read_bytes() == before
            else:
                assert generator.main(["--root", str(root)]) == 0
            result = json.loads(settings_path.read_text(encoding="utf-8"))
            assert result["editor"] == {"keep": True} and result["mcp"]["custom"] == {"keep": True}
            assert not extra_rule.exists() and not extra_skill.exists()
            if client == "qwen":
                assert not (view / "skills" / "rule-dynamic").exists()
                assert local.exists()
                assert result["mcp"]["excluded"] == ["active"]
            else:
                assert not (view / "skills" / "demo" / "SKILL.md").exists()
                assert result["mcp"]["enabledProjectMcpServers"] == ["off"]
            assert generator.main(["--root", str(root), "--check"]) == 0
            assert generator.main(["--root", str(root)]) == 0
            assert json.loads(settings_path.read_text(encoding="utf-8")) == result


def test_sync_native_artifact_path() -> None:
    script = (SCRIPTS / "sync-agent-views.sh").read_text(encoding="utf-8")
    assert 'NATIVE_MCP_ARTIFACT="${ROOT_DIR}/.doc/skil_data/harness-router/antigravity_mcp_config.json"' in script
    assert '"$ROOT_DIR" --out "$NATIVE_MCP_ARTIFACT"' in script
    assert 'copy_file_view "$NATIVE_MCP_ARTIFACT" "$env_dir/mcp.json"' in script
    assert 'copy_file_view "$NATIVE_MCP_ARTIFACT" "$env_dir/mcp_config.json"' in script
    assert 'ln -sf "$NATIVE_MCP_ARTIFACT" "$GLOBAL_GEMINI_DIR/mcp_config.json"' in script
    assert ".doc/skil_data/harness-core/antigravity_mcp_config.json" not in script

def test_r06_canon_hash_detects_cursor_rules_change() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skills = root / ".agents" / "skills"
        skills.mkdir(parents=True)
        (skills / "test-skill").mkdir()
        (skills / "test-skill" / "SKILL.md").write_text("# Test\n", encoding="utf-8")

        cursor_rules = root / ".cursor" / "rules"
        cursor_rules.mkdir(parents=True)
        rule_file = cursor_rules / "sample.mdc"
        rule_file.write_text("# Initial rule\n", encoding="utf-8")

        report_path = root / "report.json"
        initial_hash = parity.canon_hash(skills)
        report = {"status": "passed", "canon_hash": initial_hash}
        report_path.write_text(json.dumps(report), encoding="utf-8")

        # Initial check passes
        assert parity.check_freshness(report_path, skills) == []

        # Modifying .cursor/rules must change canon_hash and trigger freshness error
        rule_file.write_text("# Modified rule content\n", encoding="utf-8")
        stale_errors = parity.check_freshness(report_path, skills)
        assert any("stale" in e for e in stale_errors), f"expected stale error, got: {stale_errors}"


def test_r06_missing_view_in_check_fails() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skills = root / ".agents" / "skills"
        skills.mkdir(parents=True)
        (skills / "test-skill").mkdir()
        (skills / "test-skill" / "SKILL.md").write_text("# Test\n", encoding="utf-8")

        report_path = root / "report.json"
        initial_hash = parity.canon_hash(skills)
        report = {"status": "passed", "canon_hash": initial_hash}
        report_path.write_text(json.dumps(report), encoding="utf-8")

        missing_view = root / "non_existent_view"
        sys_argv_backup = sys.argv
        try:
            sys.argv = [
                "verify_parity.py",
                "--canonical", str(skills),
                "--manifest", str(report_path),
                "--view", str(missing_view),
                "--check",
            ]
            exit_code = parity.main()
            assert exit_code == 1, "expected exit code 1 for missing view in --check"
        finally:
            sys.argv = sys_argv_backup


def main() -> int:
    tests = [
        test_native_discovery_contract,
        test_relocated_links,
        test_tree_parity,
        test_rule_model_classification,
        test_antigravity_block_globs,
        test_rules_body_parity,
        test_manifest_freshness,
        test_mcp_view_invariants,
        test_windows_global_config_replaced,
        test_generator_stale_cleanup,
        test_kilo_fragment_lifecycle,
        test_kilo_rule_selection,
        test_windows_wsl_render,
        test_qoder_rules_and_skills,
        test_qoder_mcp_render,
        test_sync_qoder_preflight_before_writes,
        test_qwen_rules_and_mcp,
        test_qwen_enabled_transition,
        test_missing_canon_preserves_mirrors,
        test_qoder_qwen_strict_mirror_transitions,
        test_sync_native_artifact_path,
        test_parity_allow_extra,
        test_r06_canon_hash_detects_cursor_rules_change,
        test_r06_missing_view_in_check_fails,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
