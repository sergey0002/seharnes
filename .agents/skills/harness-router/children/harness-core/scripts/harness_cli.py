#!/usr/bin/env python3
"""Unified harness CLI.

Commands: doctor, sync, export, setup, mcp-audit, verify.
Runs from the project root.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "new-project/scripts"))

from lib import config, manifest, mcp, paths, ports
from lib.report import Reporter
import profile_manifest

SKILL = Path(__file__).resolve().parents[1]
ROOT_FILES = ["AGENTS.md", "mcp.index.md", ".codeprism.toml", ".cbmignore"]
HARNESS_DIRS = [".cursor", ".codex", ".kilo", ".agents", ".qoder", ".qwen", ".dsh", ".serena", ".doc/skil_data/harness-core"]


def _run(cmd: list[str], cwd: Path, timeout: int = 1800) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout: {' '.join(cmd)}"


def _copy_harness(source: Path, target: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", ".venv*", "node_modules", "vendor", "cache", "runs", "work", "state")
    for item in HARNESS_DIRS:
        src = source / item
        if not src.exists():
            continue
        dst = target / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True, ignore=ignore)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for item in ROOT_FILES:
        src = source / item
        if src.is_file():
            shutil.copy2(src, target / item)


def _extract_gate_summary(output: str, code: int) -> tuple[str, list[str]]:
    output_clean = output.strip()
    try:
        data = json.loads(output_clean)
        if isinstance(data, dict):
            errs = data.get("errors") or data.get("error") or data.get("message")
            if isinstance(errs, list) and errs:
                return str(errs[0]), [str(e) for e in errs][:5]
            if isinstance(errs, str) and errs:
                return errs, [errs]
            status = data.get("status")
            if status:
                return f"status: {status}", []
    except Exception:
        pass

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return f"exit {code}", []

    meaningful = [l for l in lines if l not in ("}", "{", "]", "[", "},", "],")]
    first_errors = [l for l in lines if any(k in l for k in ("ERROR", "DOC_MISSING", "MISSING", "failed", "DRAFT", "WARN", "NO_OWNER", "ORPHAN", "SECURITY_ERROR", "COLLISION"))][:5]
    summary = meaningful[-1] if meaningful else lines[-1]
    return summary, first_errors


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    requested = getattr(args, "checks", None)
    selected = set(requested.split(",")) if requested is not None else None
    mode = getattr(args, "mode", "standard")
    if selected is not None and (not selected or "" in selected):
        print(json.dumps({"status": "failed", "errors": ["checks must contain nonempty gate names"]}))
        return 2
    if getattr(args, "skip_gates", False) and (selected is not None or mode == "strict"):
        print(json.dumps({"status": "failed", "errors": ["--skip-gates cannot be combined with --checks or strict mode"]}))
        return 2
    if mode == "strict" and selected is not None and "structure" not in selected:
        print(json.dumps({"status": "failed", "errors": ["strict mode requires the structure gate"]}))
        return 2
    report = Reporter()
    report.step("doctor")
    errors: list[str] = []
    try:
        envs = config.load_environments(root)
        kit = config.load_kit(root)
    except ValueError as error:
        print(json.dumps({"status": "failed", "errors": [str(error)]}, ensure_ascii=False))
        return 2
    errors.extend(config.validate(envs, kit, root))
    for env in envs.get("environments", []):
        if not env.get("enabled", True):
            continue
        adapter = root / ".agents" / "skills" / "harness-router" / "children" / "harness-core" / "scripts" / "adapters" / f"{env['adapter']}.py"
        if not adapter.exists():
            errors.append(f"missing adapter: {env['adapter']}")
    for name in ("uv", "python3"):
        if shutil.which(name) is None:
            report.warn(f"missing tool: {name}")
    for item in ("AGENTS.md", ".cursor/rules", ".agents/skills"):
        if not (root / item).exists():
            errors.append(f"missing: {item}")

    gate_failures: list[str] = []
    gate_details: dict[str, dict] = {}
    if not getattr(args, "skip_gates", False):
        base = root / ".agents" / "skills" / "harness-router" / "children"
        gate_checks = [
            ("mirror-check", [sys.executable, str(base / "mirror/scripts/harness_mirror.py"), "check"]),
            ("parity", [sys.executable, str(base / "environment-sync/scripts/verify_parity.py"),
                        "--canonical", ".agents/skills", "--view", ".qoder/skills",
                        "--rules-canonical", ".cursor/rules",
                        "--rules-view", ".codex/rules", "--rules-view", ".kilo/rules",
                        "--rules-view", ".agents/rules", "--rules-view", ".qoder/rules",
                        "--manifest", ".doc/skil_data/harness-core/parity-report.json", "--check"]),
            ("qwen-view", [sys.executable, str(base / "environment-sync/scripts/generate-qwen-config.py"),
                           "--root", str(root), "--check"]),
            ("mcp-views", [sys.executable, str(base / "mcp-audit/scripts/verify_mcp_views.py"),
                           "--canonical", ".cursor/mcp.json", "--kilo", ".kilo/kilo.jsonc",
                           "--expanded", ".agents/mcp.json", "--expanded", ".qoder/settings.json",
                           "--qwen", ".qwen/settings.json", "--codex-toml", ".codex/config.toml"]),
            ("registry", [sys.executable, str(base / "improvement/scripts/validate_registry.py")]),
            ("rules", [sys.executable, str(base / "improvement/scripts/validate_rules.py"),
                       "--rules-dir", ".cursor/rules", "--skills-dir", ".agents/skills"]),
            ("structure", [sys.executable, str(base / "improvement/scripts/validate_structure.py")] + (["--json", "--junk", "--fail-on-junk", "--require-policy"] if mode == "strict" else (["--json", "--junk"] if getattr(args, "junk", False) else []))),
            ("docs-components", [sys.executable, str(base / "improvement/scripts/validate_docs.py")]),
            ("skills-format", [sys.executable, str(base / "improvement/scripts/validate_skills.py")] + (["--policy-root", str(root)] if mode == "strict" else [])),
            ("docs-scripts", [sys.executable, str(base / "doc-script/scripts/doc_script.py"), "--audit"] + (["--policy-root", str(root)] if mode == "strict" else [])),
            ("docs-skills", [sys.executable, str(base / "doc-skill/scripts/doc_skill.py"), "--audit"] + (["--policy-root", str(root)] if mode == "strict" else [])),
            ("docs-mcp", [sys.executable, str(base / "doc-mcp/scripts/doc_mcp.py"), "--audit"] + (["--policy-root", str(root)] if mode == "strict" else [])),
            ("policy-docs", [sys.executable, str(base / "harness-core/scripts/render_policy_docs.py"),
                             "--root", str(root), "--check"]),
            ("render-check", [sys.executable, str(base / "environment-sync/scripts/render_agent_views.py"),
                              "--root", str(root), "--check"]),
            ("generated-copies", [sys.executable, str(base / "environment-sync/scripts/verify_generated_copies.py"),
                                  "--root", str(root)]),
            ("native-discovery", [sys.executable, str(base / "environment-sync/scripts/generate-agent-configs.py"),
                                  str(root), "--check-discovery"]),
        ]
        unknown = sorted(selected - {name for name, _ in gate_checks}) if selected is not None else []
        if unknown:
            print(json.dumps({"status": "failed", "errors": ["unknown gates: " + ", ".join(unknown)]}))
            return 2
        for name, command in gate_checks:
            if getattr(args, "compact", False) and name in {"parity", "qwen-view", "mcp-views", "render-check", "mirror-check", "registry", "docs-components", "native-discovery"}:
                continue
            if selected is not None and name not in selected:
                continue
            code, output = _run(command, root, 300)
            structure_report = None
            if name == "structure" and (getattr(args, "junk", False) or mode == "strict"):
                try:
                    structure_report = json.loads(output)
                    if not isinstance(structure_report, dict) or any(not isinstance(structure_report.get(k), list) for k in ("errors", "warnings", "junk")):
                        raise ValueError("invalid structure report")
                    if structure_report.get("status") not in ("passed", "failed"):
                        raise ValueError("invalid structure status")
                    if structure_report["status"] == "failed" or structure_report["errors"] or (mode == "strict" and structure_report["junk"]):
                        code = code or 1
                    for category in ("errors", "warnings", "junk"):
                        for finding in structure_report[category]:
                            if not isinstance(finding, dict):
                                raise ValueError("invalid structure finding")
                            print(f"{category.upper()} {finding.get('path', '')}: {finding.get('message', finding.get('reason', ''))}")
                except (ValueError, TypeError):
                    structure_report = None
                    code = code or 1
                    output = "invalid structure JSON report"
            if code != 0:
                gate_failures.append(name)
                summary, first_errors = _extract_gate_summary(output, code)
                gate_details[name] = {"code": code, "summary": summary, "errors": first_errors}
                report.warn(f"gate {name} failed (code {code}): {summary}")
            else:
                gate_details[name] = {"code": 0, "status": "ok"}
                report.ok(f"gate {name}")
            if structure_report is not None:
                gate_details[name]["findings"] = structure_report

    if errors:
        for error in errors:
            report.warn(error)
    else:
        report.ok("configs and adapters are valid")
    report.finish()
    report.summary()
    print(json.dumps({
        "status": "failed" if (errors or gate_failures) else "passed",
        "errors": errors,
        "failed_gates": gate_failures,
        "gate_details": gate_details,
        "mode": mode,
        "scope": "selected_gates" if selected is not None else ("config_only" if getattr(args, "skip_gates", False) else "all_gates"),
        "next_action": "fix failed gates before handoff" if (errors or gate_failures) else "none",
    }, ensure_ascii=False))
    return 1 if (errors or gate_failures) else 0


def _sync_real(root: Path) -> int:
    script = root / ".agents" / "skills" / "harness-router" / "children" / "environment-sync" / "scripts" / "sync-agent-views.sh"
    if not script.is_file():
        print(f"sync script missing: {script}")
        return 2
    return _run(["bash", str(script)], root)[0]


def cmd_sync(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    envs = config.load_environments(root)
    kit = config.load_kit(root)
    errors = config.validate(envs, kit, root)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False))
        return 2

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="harness-sync-") as directory:
            temp = Path(directory)
            _copy_harness(root, temp)
            code, output = _run(["bash", str(temp / ".agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh")], temp, 600)
            if code != 0:
                print(output)
                return 1
            sync_kit = {
                "copy": [item for item in HARNESS_DIRS if not item.startswith(".doc/")],
                "rootFiles": [],
                "skipDirs": kit.get("skipDirs", []),
                "skipFiles": kit.get("skipFiles", []),
            }
            before = manifest.build(root, sync_kit)
            after = manifest.build(temp, sync_kit)
            diff = manifest.compare(after, before)
            print(json.dumps({
                "status": "dry-run",
                "overwritten_count": len(diff.overwritten),
                "added_count": len(diff.added),
                "kept_count": len(diff.target_only),
                "same": diff.same,
                "overwritten": diff.overwritten[:30],
                "added": diff.added[:30],
                "kept": diff.target_only[:30],
            }, ensure_ascii=False, indent=2))
            return 0

    if not args.yes:
        answer = input("Применить синхронизацию сред? [y/N] ").strip()
        if answer.lower() not in {"y", "yes", "д", "да"}:
            print("Отменено.")
            return 1
    code = _sync_real(root)
    print(json.dumps({"status": "passed" if code == 0 else "failed", "exit": code}, ensure_ascii=False))
    return 0 if code == 0 else 1


def cmd_export(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = Path(args.target).resolve()
    profile_key = {"Full": "developer", "Core": "core", "Developer": "developer",
                   "Project": "project"}[args.profile]
    if args.dry_run:
        kit = config.load_kit(root)
        source, excluded = profile_manifest.build(root, profile_key)
        target_all = manifest.build(target, kit) if target.is_dir() else {}
        target_map = {path: digest for path, digest in target_all.items() if path in source}
        diff = manifest.compare(source, target_map)
        print(json.dumps({
            "status": "dry-run",
            "profile": args.profile,
            "target": str(target),
            "overwritten_count": len(diff.overwritten),
            "added_count": len(diff.added),
            "kept_count": len(diff.target_only),
            "same": diff.same,
            "excluded_count": len(excluded),
            "overwritten": diff.overwritten[:30],
            "added": diff.added[:30],
            "kept": diff.target_only[:30],
            "excluded": excluded[:30],
        }, ensure_ascii=False, indent=2))
        return 0
    target = Path(args.target).resolve()
    engine = root / ".agents" / "skills" / "harness-router" / "children" / "new-project" / "scripts" / "rebase_project.ps1"
    if not engine.is_file():
        print(f"export engine missing: {engine}")
        return 2
    command = ["pwsh", "-NoProfile", "-File", str(engine), "-Target", args.target,
               "-Profile", "Core" if profile_key == "core" else "Full", "-Mode", args.mode]
    if args.project_name:
        command += ["-ProjectName", args.project_name]
    if args.yes:
        command.append("-Yes")
    if args.skip_preflight:
        command.append("-SkipPreflight")
    if args.skip_tools:
        command.append("-SkipTools")
    if args.no_review:
        command.append("-SkipReview")
    if args.no_backup:
        command.append("-SkipBackup")
    code, output = _run(command, root)
    if code == 0:
        scanner = root / ".agents" / "skills" / "harness-router" / "children" / "add-skill" / "scripts" / "scan_local_skills.py"
        baseline = target / ".doc" / "skil_data" / "harness-core" / "kit-manifest.json"
        if scanner.is_file():
            scan_code, scan_output = _run(
                ["python3", str(scanner), "--root", str(root), "--baseline", str(baseline), "--write-baseline"],
                root,
                120,
            )
            output += "\n" + scan_output
            if scan_code != 0:
                output += f"\nbaseline write failed: {scan_code}"
        else:
            output += "\nbaseline scanner not found, package manifest was not written"
    print(output)
    return code


def cmd_setup(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    script = root / ".agents" / "skills" / "harness-router" / "children" / "project-setup" / "scripts" / "onboard-project.py"
    if not script.is_file():
        print(f"setup script missing: {script}")
        return 2
    command = ["python3", str(script), "--root", str(root)]
    if args.check:
        command.append("--check")
    else:
        command.append("--yes")
    if args.php_container:
        command += ["--php-container", args.php_container]
    if args.mysql:
        command += ["--mysql", args.mysql]
    if args.mysql_database:
        command += ["--mysql-database", args.mysql_database]
    if args.mysql_port:
        command += ["--mysql-port", args.mysql_port]
    if args.serena_port:
        command += ["--serena-port", str(args.serena_port)]
    if args.web_port:
        command += ["--web-port", str(args.web_port)]
    if args.skip_indexes:
        command.append("--skip-indexes")
    code, output = _run(command, root)
    print(output)
    return code


def cmd_mcp_audit(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if getattr(args, "usage", False):
        script = root / ".agents" / "skills" / "harness-router" / "children" / "mcp-audit" / "scripts" / "scan-usage.py"
        code, output = _run(["python3", str(script), "--root", str(root)], root, 120)
        print(output)
        return code
    canon = mcp.load_canon(root)
    rows = []
    for name, server in sorted(canon.items()):
        rows.append({
            "server": name,
            "enabled": not server.get("disabled", False),
            "transport": server.get("type", "stdio"),
            "command": server.get("command") or server.get("url") or "",
        })
    print(json.dumps({"servers": rows, "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    checks = [
        ["python3", ".agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py", "--canonical", ".agents/skills", "--manifest", ".doc/skil_data/harness-core/parity-report.json", "--check"],
    ]
    failed = False
    for command in checks:
        code, output = _run(command, root, 300)
        print(output)
        failed = failed or code != 0
    return 1 if failed else 0


def cmd_setup_hooks(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(json.dumps({"status": "failed", "error": "not a git repository (.git/hooks missing)"},
                         ensure_ascii=False))
        return 2
    hook_path = hooks_dir / "pre-commit"
    if hook_path.exists() and not args.yes:
        print(f"pre-commit hook already exists: {hook_path}")
        print("Re-run with --yes to overwrite.")
        return 1
    hook = """#!/usr/bin/env bash
set -u
# Harness pre-commit gate. Runs the doctor on canonical harness edits. Bypass with
# `git commit --no-verify` only for non-harness work.
staged=$(git diff --cached --name-only)
if echo "$staged" | grep -qE '^(\\.cursor/|\\.agents/skills/)'; then
  if ! python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py --root . doctor >/dev/null 2>&1; then
    echo "BLOCKED: harness doctor failed on canonical edits"
    echo "Run: python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py --root . doctor"
    exit 1
  fi
fi
exit 0
"""
    hook_path.write_text(hook, encoding="utf-8")
    hook_path.chmod(0o755)
    print(json.dumps({"status": "passed", "hook": str(hook_path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harness management CLI")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--task", default=None, help="deprecated; the plan validator was removed")
    doctor.add_argument("--skip-gates", action="store_true", help="config/adapters checks only")
    doctor.add_argument("--junk", action="store_true", help="показать лишние файлы и каталоги")
    doctor.add_argument("--compact", action="store_true", help="skip generated-view gates in a compact reference")
    doctor.add_argument("--mode", choices=("standard", "strict"), default="standard", help="strict fails when structure detects junk")
    doctor.add_argument("--checks", help="comma-separated gate names; config checks always run")
    doctor.set_defaults(func=cmd_doctor)

    setup_hooks = sub.add_parser("setup-hooks", help="install pre-commit harness hook")
    setup_hooks.add_argument("--yes", action="store_true")
    setup_hooks.set_defaults(func=cmd_setup_hooks)

    sync = sub.add_parser("sync")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--yes", action="store_true")
    sync.add_argument("--env", action="append", default=[])
    sync.set_defaults(func=cmd_sync)

    export = sub.add_parser("export")
    export.add_argument("--target", required=True)
    export.add_argument("--project-name", default="")
    export.add_argument("--profile", choices=("Full", "Core", "Developer", "Project"), default="Full")
    export.add_argument("--mode", choices=("migrate", "clean", "update"), default="migrate")
    export.add_argument("--yes", action="store_true")
    export.add_argument("--dry-run", action="store_true")
    export.add_argument("--skip-preflight", action="store_true")
    export.add_argument("--skip-tools", action="store_true")
    export.add_argument("--no-review", action="store_true")
    export.add_argument("--no-backup", action="store_true")
    export.set_defaults(func=cmd_export)

    setup = sub.add_parser("setup")
    setup.add_argument("--check", action="store_true")
    setup.add_argument("--php-container", default="")
    setup.add_argument("--mysql", choices=("keep", "disable", "set"), default="")
    setup.add_argument("--mysql-database", default="")
    setup.add_argument("--mysql-port", default="")
    setup.add_argument("--serena-port", type=int, default=0)
    setup.add_argument("--web-port", type=int, default=0)
    setup.add_argument("--skip-indexes", action="store_true")
    setup.set_defaults(func=cmd_setup)

    audit = sub.add_parser("mcp-audit")
    audit.add_argument("--usage", action="store_true")
    audit.set_defaults(func=cmd_mcp_audit)

    verify = sub.add_parser("verify")
    verify.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
