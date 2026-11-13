"""Classify isolated nodes in the harness mirror graph.

Read-only: reads the built graph and buckets isolated nodes so a reviewer can
decide what to connect or retire. It never edits a skill or the graph.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_GRAPH = Path(".doc/skil_data/mirror/graph.json")

LEAF_HINTS = (
    "yadisk", "ponytail", "login-as-user", "kilo-config",
)


def classify(graph: dict) -> dict:
    nodes = graph.get("nodes", [])
    by_id = {}
    for node in nodes:
        nid = node.get("id") or node.get("meta", {}).get("node_id")
        if nid:
            by_id[nid] = node

    # build in/out degree from edges
    indeg = {nid: 0 for nid in by_id}
    outdeg = {nid: 0 for nid in by_id}
    for edge in graph.get("edges", []):
        src = edge.get("from") or edge.get("source")
        dst = edge.get("to") or edge.get("target")
        if src in outdeg:
            outdeg[src] += 1
        if dst in indeg:
            indeg[dst] += 1

    buckets = {"leaf-by-design": [], "should-have-trigger": [], "dead": []}
    for nid, node in by_id.items():
        if indeg.get(nid, 0) or outdeg.get(nid, 0):
            continue
        meta = node.get("meta", {})
        name = nid.split(":")[-1]
        kind = meta.get("kind") or node.get("kind", "")
        label = (meta.get("description") or node.get("label") or "").lower()
        if any(h in name or h in label for h in LEAF_HINTS):
            buckets["leaf-by-design"].append(nid)
        elif "trigger" in label or "когда" in label or meta.get("always_apply") is not None:
            buckets["should-have-trigger"].append(nid)
        else:
            buckets["dead"].append(nid)
    return {k: v for k, v in buckets.items()}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Classify isolated mirror nodes")
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.graph.is_file():
        print(json.dumps({"status": "failed", "error": f"graph missing: {args.graph}"}))
        return 2
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    buckets = classify(graph)
    if args.json:
        print(json.dumps({"counts": {k: len(v) for k, v in buckets.items()},
                          "buckets": buckets}, ensure_ascii=False, indent=2))
    else:
        for name, items in buckets.items():
            print(f"{name}: {len(items)}")
            for it in items[:5]:
                print("  ", it)
    return 0


if __name__ == "__main__":
    sys.exit(main())
