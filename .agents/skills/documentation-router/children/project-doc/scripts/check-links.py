#!/usr/bin/env python3
"""Check local markdown links under .doc.

Skips code fences/inline code, external URLs and internal zones
(.doc/**/_jsondoc, vendor).

--root may point either at the project root or at the .doc directory itself.
--only limits the scan to one subdirectory of .doc. Exit 1 if any local link
target is missing, exit 2 when the scan directory does not exist.

Usage:
  python3 .agents/skills/documentation-router/children/project-doc/scripts/check-links.py [--root .] [--only harnes]
"""
import argparse, collections, pathlib, re, sys, urllib.parse

FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    return INLINE.sub("", FENCE.sub("", text))


def links(text: str):
    i, n = 0, len(text)
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        depth, j = 0, i
        while j < n:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= n or j + 1 >= n or text[j + 1] != "(":
            i += 1
            continue
        k, par = j + 2, 1
        while k < n and par > 0:
            if text[k] == "(":
                par += 1
            elif text[k] == ")":
                par -= 1
            k += 1
        if par == 0:
            yield text[i + 1:j], text[j + 2:k - 1]
            i = k
        else:
            i += 1


def is_external(target: str) -> bool:
    t = target.strip()
    if t.startswith("<") and t.endswith(">"):
        return True
    return t.lower().startswith(
        ("http://", "https://", "mailto:", "tel:", "#", "/", "data:", "ftp:", "file:"))


def check_text(text: str, base: pathlib.Path) -> list[str]:
    broken = []
    for _text, target in links(strip_code(text)):
        t = target.strip()
        if not t or is_external(t):
            continue
        local = urllib.parse.unquote(t.split("#", 1)[0])
        if not local:
            continue
        if not (base / local).resolve().exists():
            broken.append(t)
    return broken


def check_file(path: pathlib.Path) -> list[str]:
    return check_text(path.read_text(encoding="utf-8", errors="ignore"),
                      path.parent)


def docs_dir(root: pathlib.Path) -> pathlib.Path:
    return root if root.name == ".doc" else root / ".doc"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--only", default="", help="scan only this subdirectory of .doc")
    ap.add_argument("--skip", action="append", default=[], help="skip a directory name inside the scan scope")
    ap.add_argument("--skip-historical", action="store_true", help="skip docs with status: deprecated or frozen")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()
    docs = docs_dir(root)
    if not docs.is_dir():
        print(f"ERROR: docs directory not found: {docs}", file=sys.stderr)
        return 2
    scan = docs
    if args.only:
        scan = docs / args.only
        if not scan.is_dir():
            print(f"ERROR: scan directory not found: {scan}", file=sys.stderr)
            return 2
    broken = []
    for path in scan.rglob("*.md"):
        if "_jsondoc" in path.parts or "vendor" in path.parts:
            continue
        if set(path.relative_to(scan).parts[:-1]) & set(args.skip):
            continue
        if args.skip_historical:
            head = path.read_text(encoding="utf-8", errors="ignore")[:800]
            match = re.search(r"^status:\s*(\S+)", head, re.M)
            if match and match.group(1) in ("deprecated", "frozen"):
                continue
        for target in check_file(path):
            broken.append((path, target))
    if broken:
        by_dir = collections.Counter(str(p.parent) for p, _ in broken)
        for directory, count in by_dir.most_common(5):
            print(f"{count:4d}  {directory}")
        for path, target in broken[:20]:
            print(f"{path.relative_to(root)} -> {target}")
        print(f"TOTAL broken links: {len(broken)}")
        return 1
    if not args.quiet:
        print("links: OK, 0 broken")
    return 0


if __name__ == "__main__":
    sys.exit(main())
