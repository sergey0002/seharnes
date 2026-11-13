#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import contextlib
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from runtime_registration import check
from validate_registry import validate as validate_registry
from validate_rules import validate
from validate_skills import Checker


def write_skill(skill: Path, name: str, scripts: list[str]) -> None:
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test skill\n---\n", encoding="utf-8")
    (skill / "README.md").write_text("test\n", encoding="utf-8")
    (skill / "skill.json").write_text(json.dumps({
        "schema": 1,
        "name": name,
        "kind": "leaf",
        "entry": "SKILL.md",
        "readme": "README.md",
        "resources": {"scripts": scripts, "references": [], "assets": []},
        "tests": [],
        "children": [],
        "dependencies": {"skills": [], "project": []},
        "generated": [],
    }), encoding="utf-8")


def test_structure_checks() -> None:
    from validate_structure import DEFAULT_LAYOUT, collect
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name in ("one", "two"):
            skill = root / ".agents" / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n", encoding="utf-8")
        (root / ".agents" / "skills" / "one" / "SKILL.md").write_text(
            "---\nname: one\ndescription: test\n---\n"
            ".doc/skil_data/one/screenshots/a.png\n"
            ".doc/skil_data/one/tmp/a.cookies\n"
            ".doc/skil_data/ghost/a.md\n",
            encoding="utf-8",
        )
        rules = root / ".cursor" / "rules"
        rules.mkdir(parents=True)
        (rules / "a.mdc").write_text(".doc/skil_data/ghost/a.md\n", encoding="utf-8")
        errors, _warnings, _junk = collect(root, DEFAULT_LAYOUT)
        codes = {item["code"] for item in errors}
        assert {"S10", "S11", "S12"} <= codes, codes


def test_layout_policy_is_read_and_invalid_syntax_rejected() -> None:
    from validate_structure import load_layout
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = root / '.doc/harnes/state/canon-paths.yaml'
        policy.parent.mkdir(parents=True)
        policy.write_text('layout:\n  scripts:\n    system: "other/scripts"\n'
                          '  docs:\n    mcp_disabled: "other/archive"\n'
                          '  forbidden_roots:\n    - "old/scripts"\n', encoding='utf-8')
        layout = load_layout(root)
        assert layout['system'] == 'other/scripts'
        assert layout['mcp_disabled'] == 'other/archive'
        assert layout['forbidden_roots'] == ['old/scripts']
        for text in ('layout:\n  scripts:\n    system: "../escape"\n',
                     'layout:\n  scripts:\n    typo: "other"\n',
                     'layout:\n  temp_dir: "a"\n  temp_dir: "b"\n',
                     'layout:\n  temp_dir: unquoted\n'):
            policy.write_text(text, encoding='utf-8')
            try:
                load_layout(root)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid layout unexpectedly accepted: ' + text)


def test_relative_mcp_command_is_resolved_in_checked_project() -> None:
    from validate_structure import DEFAULT_LAYOUT, collect
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / 'project'
        (root / '.cursor').mkdir(parents=True)
        (root / '.cursor/mcp.json').write_text(json.dumps({'mcpServers': {
            'fixture': {'command': 'python', 'args': ['./tool.py']}}}), encoding='utf-8')
        (base / 'tool.py').write_text('pass\n', encoding='utf-8')
        previous = Path.cwd()
        try:
            os.chdir(base)
            errors, _, _ = collect(root, DEFAULT_LAYOUT)
        finally:
            os.chdir(previous)
        assert any(item['code'] == 'S07' and './tool.py' in item['message'] for item in errors)


def test_state_policy_does_not_require_directory_named_state() -> None:
    from validate_structure import DEFAULT_LAYOUT, collect
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        state = root / 'other/history'
        state.mkdir(parents=True)
        (state / 'current.md').write_text('Use .cursor/scripts/tool.py\n', encoding='utf-8')
        layout = {**DEFAULT_LAYOUT, 'state': 'other/history'}
        errors, warnings, _ = collect(root, layout)
        assert not any(item['code'] == 'S09' for item in errors)
        assert any(item['code'] == 'S09' for item in warnings)


def test_junk_scan_does_not_mark_test_runtime_output_for_deletion() -> None:
    from validate_structure import DEFAULT_LAYOUT, collect_junk
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / '.tools/codeception/tests/_output/run.log'
        output.parent.mkdir(parents=True)
        output.write_text('active test log', encoding='utf-8')
        junk = root / '.agents/skills/sample/scripts/__pycache__/sample.pyc'
        junk.parent.mkdir(parents=True)
        junk.write_bytes(b'cache')
        found = {item['path'] for item in collect_junk(root, DEFAULT_LAYOUT)}
        assert '.tools/codeception/tests/_output/run.log' not in found
        assert '.agents/skills/sample/scripts/__pycache__/sample.pyc' in found


def test_junk_json_status_matches_exit_code() -> None:
    import validate_structure
    with tempfile.TemporaryDirectory() as directory:
        for strict in (False, True):
            args = ['validate_structure.py', '--root', directory, '--json', '--junk']
            if strict:
                args.append('--fail-on-junk')
            output = io.StringIO()
            with patch.object(sys, 'argv', args), patch.object(validate_structure, 'collect', return_value=([], [], [])), \
                    patch.object(validate_structure, 'collect_junk', return_value=[{'path': 'x.tmp', 'reason': 'tmp'}]), \
                    contextlib.redirect_stdout(output):
                code = validate_structure.main()
            assert code == (1 if strict else 0)
            assert json.loads(output.getvalue())['status'] == ('failed' if strict else 'passed')


def test_required_policy_missing_fails_without_fallback() -> None:
    import validate_structure
    with tempfile.TemporaryDirectory() as directory:
        args = ['validate_structure.py', '--root', directory, '--json', '--require-policy']
        output = io.StringIO()
        with patch.object(sys, 'argv', args), contextlib.redirect_stdout(output):
            code = validate_structure.main()
        report = json.loads(output.getvalue())
        assert code == 1 and report['status'] == 'failed'
        assert report['errors'][0]['code'] == 'POLICY'


def test_required_policy_checks_its_own_identity() -> None:
    from validate_structure import require_canonical_policy
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        policy = root / '.doc/harnes/state/canon-paths.yaml'
        policy.parent.mkdir(parents=True)
        entry = '  path_manifest: ".doc/harnes/state/canon-paths.yaml"\n'
        prefix = ('schema_version: 1\nmanifest:\n  path: ".doc/harnes/state/canon-paths.yaml"\n'
                  '  role: "policy"\n  owner: "harness-core"\n  required_profiles:\n'
                  '    - "core"\n    - "developer"\n    - "project"\n')
        suffix = 'layout:\n  temp_dir: "temp"\n'
        policy.write_text(prefix + 'canonical_roots:\n' + entry + suffix, encoding='utf-8')
        with patch('validate_structure.require_preliminary_policies'):
            require_canonical_policy(root)
        for body in (prefix + 'canonical_roots:\n  other: "x"\n' + suffix,
                     prefix + 'canonical_roots:\n  path_manifest: "other.yaml"\n' + suffix,
                     prefix + 'canonical_roots:\n' + entry + entry + suffix,
                     prefix + 'canonical_roots:\n  path_manifest: unquoted\n' + suffix,
                     prefix.replace('schema_version: 1', 'schema_version: 2') + 'canonical_roots:\n' + entry + suffix,
                     prefix.replace('    - "project"\n', '') + 'canonical_roots:\n' + entry + suffix):
            policy.write_text(body, encoding='utf-8')
            try:
                require_canonical_policy(root)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid policy identity accepted')
        try:
            policy.unlink()
            policy.symlink_to(root / 'outside.yaml')
        except (OSError, NotImplementedError):
            return
        try:
            require_canonical_policy(root)
        except ValueError:
            pass
        else:
            raise AssertionError('symbolic link accepted as policy')


def test_required_policy_checks_preliminary_bundle() -> None:
    from validate_structure import require_canonical_policy
    source = Path(__file__).resolve().parents[6]
    relatives = ('.doc/harnes/state/canon-paths.yaml',
                 '.agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml',
                 '.agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for relative in relatives:
            dst = root / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((source / relative).read_bytes())
        require_canonical_policy(root)
        (root / relatives[-1]).unlink()
        try:
            require_canonical_policy(root)
        except ValueError as error:
            assert 'POLICY_MISSING' in str(error)
        else:
            raise AssertionError('missing component policy accepted')


def test_skill_policy_tightens_but_cannot_relax_trusted_rules() -> None:
    source = Path(__file__).resolve().parents[6]
    core = source / '.agents/skills/harness-router/children/harness-core/scripts'
    sys.path.insert(0, str(core))
    try:
        from canon_paths import load_preliminary_policies
        original = load_preliminary_policies(source)['skill_format']['rules']
        policy = {key: dict(value) for key, value in original.items()}
        rule = dict(policy['SF02'])
        rule['allowed_frontmatter'] = tuple(x for x in rule['allowed_frontmatter'] if x != 'license') + ('untrusted-field',)
        policy['SF02'] = rule
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / 'example'
            write_skill(skill, 'example', [])
            (skill / 'SKILL.md').write_text('---\nname: example\ndescription: test\nlicense: MIT\nuntrusted-field: x\n---\n', encoding='utf-8')
            errors, _ = Checker(root, policy).run()
            messages = [error['message'] for error in errors if error['code'] == 'V05']
            assert any('license' in message for message in messages)
            assert any('untrusted-field' in message for message in messages)
            rule['name_pattern'] = '.*'
            try:
                Checker(root, policy)
            except ValueError:
                pass
            else:
                raise AssertionError('weakened name pattern accepted')
    finally:
        sys.path.remove(str(core))


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rules = root / "rules"
        skills = root / "skills"
        (rules / "a.mdc").parent.mkdir(parents=True)
        (skills / "one").mkdir(parents=True)
        (rules / "a.mdc").write_text("alwaysApply: true\nuse for: shared\nSee one/SKILL.md and missing/scripts/no.py\n", encoding="utf-8")
        (skills / "one" / "SKILL.md").write_text("---\nname: one\n---\nTriggers: shared\n", encoding="utf-8")
        report = validate(rules, skills)
        assert report["status"] == "failed"
        assert any(item["kind"] == "missing_script_reference" for item in report["issues"])
        assert any(item["kind"] == "duplicate_trigger" for item in report["issues"])
        # P12: first run creates the delta baseline, second run diffs it.
        assert report["delta"] is None
        again = validate(rules, skills)
        assert again["delta"] is not None
        assert again["delta"]["unchanged"] == len(report["issues"])
        assert again["delta"]["added"] == [] and again["delta"]["removed"] == []
        assert validate_registry(Path(__file__).resolve().parents[1] / "scripts" / "component_registry.json") == []
        assert check("harness-improvement", Path.cwd(), [root / "missing.json"])["runtime_registration"]["status"] == "fallback"
        assert check("harness-improvement", Path.cwd(), [Path(__file__)])["runtime_registration"]["status"] == "n/a"
        nested = root / "nested"
        write_skill(nested / "parent", "parent", [])
        child = nested / "parent" / "children" / "child"
        write_skill(child, "child", [])
        (child / "scripts").mkdir()
        (child / "scripts" / "undeclared.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        nested_errors, _ = Checker(nested).run()
        assert any(item["code"] == "V11" and "undeclared.sh" in item["message"] for item in nested_errors)
    test_structure_checks()
    test_layout_policy_is_read_and_invalid_syntax_rejected()
    test_relative_mcp_command_is_resolved_in_checked_project()
    test_state_policy_does_not_require_directory_named_state()
    test_junk_scan_does_not_mark_test_runtime_output_for_deletion()
    test_junk_json_status_matches_exit_code()
    test_required_policy_missing_fails_without_fallback()
    test_required_policy_checks_its_own_identity()
    test_required_policy_checks_preliminary_bundle()
    test_skill_policy_tightens_but_cannot_relax_trusted_rules()
    print("harness improvement tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
