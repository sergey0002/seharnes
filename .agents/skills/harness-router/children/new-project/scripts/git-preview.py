#!/usr/bin/env python3
"""Preview explicit paths from a local bare Git store without applying changes."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from transfer_git import discover_git_paths, plan_selected_git_update, snapshot_git_blobs
from transfer_inventory import discover_target_paths
from transfer_local import selected_local_paths, validate_local_extension
from transfer_plan import _root_path
from transfer_receipt import read_preview_receipt, receipt_paths_in_roots
from transfer_report import summarize_preview
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness-core/scripts"))
from canon_paths import read_policy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="trusted local bare Git object store")
    parser.add_argument("--commit", required=True, help="full pinned commit object ID")
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument("--base-commit", help="unverified historical commit for comparison, not an installation receipt")
    baseline.add_argument("--use-receipt", action="store_true", help="read unverified target receipt for scoped preview")
    parser.add_argument("--target", required=True, type=Path, help="existing or not-yet-created project root")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--path", action="append", help="explicit relative path; repeat for each file")
    selection.add_argument("--root", action="append", help="discover tracked files under this relative Git root")
    parser.add_argument("--local", action="append", default=[], help="selected path owned by the target")
    parser.add_argument("--use-local-policy", action="store_true", help="read target local declarations for scoped preview")
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args(argv)
    try:
        protected = []
        local_paths = list(args.local)
        components = None
        receipt = None
        receipt_info = None
        if args.use_receipt:
            if args.root is None:
                raise ValueError("receipt preview requires --root")
            target_root = _root_path(args.target, must_exist=True)
            receipt_dir = _root_path(target_root / ".doc/web/state/transfer", must_exist=True)
            receipt, receipt_info = read_preview_receipt(receipt_dir / "receipt.json")
        if args.use_local_policy and (args.root is None or not (args.base_commit or args.use_receipt)):
            raise ValueError("local policy preview requires --root and a historical baseline")
        if args.path is not None:
            paths = args.path
        else:
            git_paths = discover_git_paths(args.repo, args.commit, args.root)
            base_paths = discover_git_paths(args.repo, args.base_commit, args.root) if args.base_commit else []
            if receipt is not None:
                base_paths = receipt_paths_in_roots(list(receipt), args.root)
            target_root = _root_path(args.target, must_exist=False)
            target_paths, protected = discover_target_paths(target_root, args.root)
            paths = sorted(set(git_paths) | set(base_paths) | set(target_paths))
            if args.use_local_policy:
                policy_dir = _root_path(target_root / ".doc/harnes/state", must_exist=True)
                policy = read_policy(policy_dir / "canon-paths.local.yaml")
                components = validate_local_extension(policy, base_paths, args.root)
                local_paths = sorted(set(local_paths) | set(selected_local_paths(paths, components)))
        if not paths:
            raise ValueError("no files found under selected roots")
        if len(paths) > 2000:
            raise ValueError("too many selected paths")
        historical = (snapshot_git_blobs(args.repo, args.base_commit, paths, max_file_bytes=args.max_file_bytes)
                      if args.base_commit else ({p: receipt[p] for p in paths if p in receipt} if receipt is not None else None))
        if receipt is not None and set(local_paths) & set(historical):
            raise ValueError("LOCAL_POLICY_ESCALATION: local path overlaps receipt")
        base = {path: state for path, state in historical.items() if path not in local_paths} if historical is not None else None
        result = plan_selected_git_update(repo=args.repo, commit=args.commit, target=args.target,
                                          paths=paths, receipt=base, local_paths=local_paths,
                                          max_file_bytes=args.max_file_bytes)
        result['directory_summary'] = summarize_preview(result['files'])
        if historical is not None:
            for row in result['files']:
                if row['path'] in local_paths and row['path'] in historical:
                    row['historical_base_not_ownership'] = asdict(historical[row['path']])
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 2
    result.update({"status": "preview_only", "base": ("receipt_unverified" if args.use_receipt else
                   "historical_commit_unverified" if args.base_commit else "unknown"),
                   "base_commit": args.base_commit, "release_trust": "not_verified"})
    if receipt_info is not None:
        result["receipt"] = receipt_info
    if args.root is not None:
        result.update({"scope": "selected_roots_preview", "roots": args.root,
                       "target_only_discovery": True, "protected_paths_not_read": protected})
    if components is not None:
        result.update({"local_policy": ("scoped_receipt_check_only_not_ownership_proof" if args.use_receipt else
                                        "scoped_historical_check_only_not_ownership_proof"),
                       "local_components": list(components)})
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
