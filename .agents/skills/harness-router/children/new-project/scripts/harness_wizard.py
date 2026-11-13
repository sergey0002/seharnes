#!/usr/bin/env python3
"""Interactive or flag-driven master for the read-only transfer preview.

The wizard asks for the three independent choices from the migration plan
(source, operation, target) and then delegates to harness_transfer.py plan.
It does not copy files, approve conflicts or apply changes.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_transfer


def _ask(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"missing value: {label}")


def _missing(args) -> list[str]:
    missing = []
    if not args.target:
        missing.append("--target")
    if not args.profile:
        missing.append("--profile")
    if args.source_kind == "git":
        if not args.repo:
            missing.append("--repo")
        if not args.commit:
            missing.append("--commit")
    elif not args.source:
        missing.append("--source")
    if not args.root and not args.path:
        missing.append("--root or --path")
    return missing


def _fill_interactive(args) -> None:
    if not args.source_kind:
        args.source_kind = _ask("Источник kit: local или git", "local")
    if args.source_kind not in ("local", "git"):
        raise ValueError("source kind must be local or git")
    if args.source_kind == "git":
        args.repo = args.repo or _ask("Локальное bare-хранилище Git")
        args.commit = args.commit or _ask("Полный commit SHA")
    else:
        args.source = args.source or _ask("Каталог локального исходника")
    args.target = args.target or _ask("Каталог проекта")
    if not args.profile:
        args.profile = _ask("Профиль: core, developer или project", "core")
    if not args.operation:
        args.operation = _ask("Операция: install или update", "update")
    if not args.root and not args.path:
        roots = _ask("Корни через запятую (пусто, чтобы задать пути)", "")
        if roots:
            args.root = [item.strip() for item in roots.split(",") if item.strip()]
        else:
            args.path = [item.strip() for item in _ask("Явные пути через запятую").split(",") if item.strip()]


def _transfer_argv(args) -> list[str]:
    argv = ["plan", "--source-kind", args.source_kind, "--target", args.target,
            "--profile", args.profile, "--operation", args.operation]
    if args.source_kind == "git":
        argv += ["--repo", args.repo, "--commit", args.commit]
    else:
        argv += ["--source", args.source]
    for root in args.root or []:
        argv += ["--root", root]
    for path in args.path or []:
        argv += ["--path", path]
    if args.base_commit:
        argv += ["--base-commit", args.base_commit]
    if args.release_manifest:
        argv += ["--release-manifest", args.release_manifest]
    if args.use_receipt:
        argv.append("--use-receipt")
    for path in args.local or []:
        argv += ["--local", path]
    if args.use_local_policy:
        argv.append("--use-local-policy")
    if args.max_file_bytes:
        argv += ["--max-file-bytes", str(args.max_file_bytes)]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-kind", choices=("local", "git"))
    parser.add_argument("--source")
    parser.add_argument("--repo")
    parser.add_argument("--commit")
    parser.add_argument("--target")
    parser.add_argument("--profile", choices=("core", "developer", "project"))
    parser.add_argument("--operation", choices=("install", "update"))
    parser.add_argument("--root", action="append")
    parser.add_argument("--path", action="append")
    parser.add_argument("--base-commit")
    parser.add_argument("--release-manifest")
    parser.add_argument("--use-receipt", action="store_true")
    parser.add_argument("--local", action="append")
    parser.add_argument("--use-local-policy", action="store_true")
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    args = parser.parse_args(argv)
    interactive = not args.non_interactive
    if interactive and not sys.stdin.isatty():
        print(json.dumps({"status": "failed", "reason": "use --non-interactive without a TTY"}, ensure_ascii=False))
        return 3
    try:
        if interactive:
            _fill_interactive(args)
        missing = _missing(args)
        if missing:
            raise ValueError("missing required choices: " + ", ".join(missing))
        if interactive and not args.yes:
            summary = (f"Источник: {args.source_kind}\nПрофиль: {args.profile}\n"
                       f"Операция: {args.operation}\nTarget: {args.target}")
            print(summary)
            if input("Построить предпросмотр? [y/N]: ").strip().lower() not in ("y", "yes", "д", "да"):
                print(json.dumps({"status": "cancelled"}, ensure_ascii=False))
                return 0
    except (EOFError, ValueError) as error:
        print(json.dumps({"status": "failed", "reason": str(error) or "input failed"}, ensure_ascii=False))
        return 3
    return harness_transfer.main(_transfer_argv(args))


if __name__ == "__main__":
    raise SystemExit(main())
