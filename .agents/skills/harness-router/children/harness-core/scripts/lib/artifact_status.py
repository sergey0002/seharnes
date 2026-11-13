"""Claimed status for harness artifacts.

The plan validator was removed from the harness, so this module reports the
declared status only. It never runs a verifier and never rewrites artifact files.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

VERIFIER_VERSION = "2026.11"

META_RE = re.compile(r"(?ms)^<!--\s*meta\b(.*?)-->")
STATUS_KEYS = ("audit_status", "status", "test_status")


@dataclass
class ArtifactStatus:
    path: str
    declared: str
    status: str            # "claimed" | "verified" | "absent"
    verified_by: str = ""
    verifier_version: str = ""
    inputs_sha256: str = ""
    detail: str = ""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _declared_status(text: str) -> str:
    """Return the first declared status value in the meta block, or empty."""
    m = META_RE.search(text)
    scope = m.group(1) if m else text
    for key in STATUS_KEYS:
        found = re.search(rf"(?im)^\s*{key}\s*:\s*(\S+)", scope)
        if found:
            return found.group(1).strip().strip("'\"")
    return ""


def read_status(path: Path) -> ArtifactStatus:
    """Read declared status without running any verifier (claimed/absent)."""
    path = Path(path)
    if not path.is_file():
        return ArtifactStatus(str(path), "", "absent", detail="file not found")
    text = path.read_text(encoding="utf-8", errors="replace")
    declared = _declared_status(text)
    digest = file_sha256(path)
    if not declared:
        return ArtifactStatus(str(path), "", "absent", inputs_sha256=digest,
                              detail="no declared status in meta")
    return ArtifactStatus(str(path), declared, "claimed", inputs_sha256=digest,
                          detail="declaration only; run --verify to confirm")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Read an artifact status")
    ap.add_argument("path", type=Path, help="artifact file (plan.md)")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    status = read_status(args.path)

    payload = asdict(status)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{payload['status']}\t{payload['path']}\t{payload['detail']}")
    return 0 if payload["status"] in ("verified", "claimed") else 1


if __name__ == "__main__":
    sys.exit(main())
