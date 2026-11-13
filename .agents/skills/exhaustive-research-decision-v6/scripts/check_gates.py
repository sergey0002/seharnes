#!/usr/bin/env python3
"""Validate v6 research-decision artifacts.

Usage:
    python scripts/check_gates.py --init-v6 research/<task-id> [--force]
    python scripts/check_gates.py research/<task-id>

Exit code 0 = PASS, 1 = FAIL/INCOMPLETE, 2 = usage/IO error.
No third-party dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "assets" / "templates"

REQUIRED_FILES = [
    "00-brief.md", "00-state.md", "99-handoff.md", "task-spec.md",
    "research-protocol.md", "candidates.csv", "adoption-evidence.csv",
    "feature-dictionary.csv", "feature-evidence.csv", "criteria.csv",
    "synthetic-scores.csv", "gaps.csv", "decision-matrix.csv",
    "research-assignments.csv", "sources.csv", "claims.csv",
    "method-registry.md", "contradictions.csv", "critique-log.csv",
    "reuse-decision.md", "build-justification.md", "deviation-request.md",
    "context-budget.md", "verification.md", "compliance-matrix.csv",
    "sensitivity.md", "final-report.md", "gates.json",
]

REQUIRED_HEADERS = {
    "candidates.csv": ["candidate_id", "candidate_type", "name", "version", "proven_use", "source_ids", "method_ids", "status"],
    "adoption-evidence.csv": ["candidate_id", "evidence_type", "source_ids", "excerpt", "date", "version", "independence_group", "confidence"],
    "feature-dictionary.csv": ["feature_id", "canonical_name", "aliases", "definition", "unit", "direction", "source_ids", "method_ids", "version_scope"],
    "feature-evidence.csv": ["candidate_id", "feature_id", "value", "normalized_value", "status", "source_ids", "excerpt", "location", "date", "version", "contradiction_ids", "method_ids"],
    "criteria.csv": ["criterion_id", "name", "origin", "type", "unit", "direction", "applies_to_all", "na_policy", "formula", "input_feature_ids", "weight", "hard_gate", "source_ids", "method_ids", "decision_critical", "synthetic", "owner", "status"],
    "synthetic-scores.csv": ["score_id", "criterion_id", "formula", "input_feature_ids", "normalization", "method_ids", "sensitivity_status", "status"],
    "gaps.csv": ["gap_id", "link_type", "link_id", "owner", "status", "evidence"],
    "decision-matrix.csv": ["candidate_id", "criterion_id", "raw_value", "normalized", "score", "source_ids", "method_ids", "status", "notes"],
    "research-assignments.csv": ["assignment_id", "linked_ids", "objective", "scope_in", "scope_out", "method_ids", "assigned_agent", "input_files", "output_file", "stop_condition", "return_schema", "max_summary_tokens", "wave", "status"],
    "sources.csv": ["source_id", "url", "document_name", "type", "tier", "date", "version", "location", "excerpt", "independence_group", "claim_ids", "method_ids", "retrieval_date"],
    "claims.csv": ["claim_id", "statement", "decision_critical", "source_ids", "method_ids", "verification_status", "qualification", "contradiction_ids"],
    "contradictions.csv": ["contradiction_id", "claim_a", "claim_b", "source_a", "source_b", "resolution", "status", "method_ids"],
    "critique-log.csv": ["critique_id", "gate", "critic", "artifact", "finding", "severity", "status", "refinement_id", "source_ids", "method_ids"],
    "compliance-matrix.csv": ["standard_id", "requirement", "artifact", "status", "score", "gap", "owner", "method_ids"],
}

CHECK_FIELDS = {
    "candidates.csv": [("candidate_id", False), ("candidate_type", False), ("name", False), ("version", False), ("proven_use", False), ("source_ids", False), ("method_ids", False), ("status", False)],
    "adoption-evidence.csv": [("candidate_id", False), ("evidence_type", False), ("source_ids", False), ("excerpt", False), ("date", False), ("version", False), ("independence_group", False), ("confidence", False)],
    "feature-dictionary.csv": [("feature_id", False), ("canonical_name", False), ("definition", False), ("unit", False), ("direction", False), ("source_ids", False), ("method_ids", False), ("version_scope", False)],
    "feature-evidence.csv": [("candidate_id", False), ("feature_id", False), ("value", False), ("normalized_value", False), ("status", False), ("source_ids", False), ("excerpt", False), ("location", False), ("date", False), ("version", False), ("method_ids", False)],
    "criteria.csv": [("criterion_id", False), ("name", False), ("origin", False), ("type", False), ("unit", False), ("direction", False), ("applies_to_all", False), ("na_policy", False), ("source_ids", False), ("method_ids", False), ("decision_critical", False), ("synthetic", False), ("owner", False), ("status", False)],
    "synthetic-scores.csv": [("score_id", False), ("criterion_id", False), ("formula", False), ("input_feature_ids", False), ("normalization", False), ("method_ids", False), ("sensitivity_status", False), ("status", False)],
    "gaps.csv": [("gap_id", False), ("link_type", False), ("link_id", False), ("owner", False), ("status", False), ("evidence", False)],
    "decision-matrix.csv": [("candidate_id", False), ("criterion_id", False), ("raw_value", False), ("normalized", False), ("score", False), ("source_ids", False), ("method_ids", False), ("status", False), ("notes", False)],
    "research-assignments.csv": [("assignment_id", False), ("objective", False), ("method_ids", False), ("assigned_agent", False), ("output_file", False), ("stop_condition", False), ("status", False)],
    "sources.csv": [("source_id", False), ("url", False), ("document_name", False), ("type", False), ("tier", False), ("date", False), ("version", False), ("location", False), ("excerpt", False), ("independence_group", False), ("claim_ids", True), ("method_ids", False), ("retrieval_date", False)],
    "claims.csv": [("claim_id", False), ("statement", False), ("decision_critical", False), ("source_ids", False), ("method_ids", False), ("verification_status", False)],
    "contradictions.csv": [("contradiction_id", False), ("claim_a", True), ("claim_b", True), ("source_a", True), ("source_b", True), ("resolution", True), ("status", False), ("method_ids", False)],
    "critique-log.csv": [("critique_id", False), ("gate", False), ("critic", False), ("artifact", False), ("finding", False), ("severity", False), ("status", False), ("source_ids", False), ("method_ids", False)],
    "compliance-matrix.csv": [("standard_id", False), ("requirement", False), ("artifact", False), ("status", False), ("score", False), ("gap", True), ("owner", False), ("method_ids", False)],
}

GATES = [
    "BRIEF", "REUSE_FIRST", "CANDIDATE_ADOPTION", "UNION_COMPLETE",
    "GAP_FILLING", "CRITERIA_TRANSPARENCY", "SYNTHETIC_TRANSPARENCY",
    "MATRIX_COMPLETE", "ASSIGNMENT", "PROVENANCE", "CONTRADICTION",
    "CRITIQUE", "SENSITIVITY", "VERIFICATION", "HUMAN_GATE",
    "OUTPUT_CONTRACT", "CONTEXT_BUDGET", "RESIDUAL_UNKNOWNS", "NO_FAKE_PASS",
]

PLACEHOLDERS = {"todo", "tbd", "unknown", "<...>", "yyyy-mm-dd", "1970-01-01t00:00:00+00:00", "init", "draft", "open", "incomplete", "unchecked"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def bad(value: str | None, allow_dash: bool = False) -> bool:
    v = (value or "").strip()
    low = v.lower()
    if allow_dash and v in {"—", "-"}:
        return False
    if not v or v in {"—", "-"}:
        return True
    if low in PLACEHOLDERS:
        return True
    if "todo" in low or "tbd" in low or ("<" in v and ">" in v):
        return True
    if low.startswith("1970-01-01"):
        return True
    return False


def read_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line.strip())
        if m:
            out[m.group(1).lower()] = m.group(2).strip()
    return out


def read_csv(path: Path, rep: Report) -> list[dict[str, str]]:
    if not path.exists():
        rep.error(f"missing file: {path.name}")
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        headers = reader.fieldnames or []
    for col in REQUIRED_HEADERS.get(path.name, []):
        if col not in headers:
            rep.error(f"{path.name}: missing column '{col}'")
    return rows


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def require_kv(kv: dict[str, str], key: str, rep: Report, filename: str, allow_dash: bool = False) -> str:
    val = kv.get(key, "")
    if bad(val, allow_dash=allow_dash):
        rep.error(f"{filename}: missing/placeholder '{key}'")
    return val


def init_v6(target: Path, force: bool) -> int:
    if target.exists() and any(target.iterdir()) and not force:
        print("ERROR: target is not empty; use --force", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    for src in sorted(TEMPLATES.iterdir()):
        if src.is_file():
            shutil.copy2(src, target / src.name)
    gates = {
        "status": "INIT",
        "task_dir": str(target),
        "errors": 0,
        "warnings": 0,
        "gates_closed": [],
        "residual_unknowns": ["fresh init"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "freedom_profile": "balanced",
    }
    (target / "gates.json").write_text(json.dumps(gates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"INIT-V6 OK: {target}")
    return 0


def check_v6(target: Path) -> int:
    rep = Report()
    if not target.is_dir():
        print("ERROR: not a directory", file=sys.stderr)
        return 2

    for name in REQUIRED_FILES:
        if not (target / name).exists():
            rep.error(f"missing file: {name}")

    data = {name: read_csv(target / name, rep) for name in REQUIRED_HEADERS}
    brief = read_kv(target / "00-brief.md")
    state = read_kv(target / "00-state.md")
    task = read_kv(target / "task-spec.md")
    protocol = read_kv(target / "research-protocol.md")
    reuse = read_kv(target / "reuse-decision.md")
    build = read_kv(target / "build-justification.md")
    deviation = read_kv(target / "deviation-request.md")
    budget = read_kv(target / "context-budget.md")
    verification = read_kv(target / "verification.md")
    final = read_kv(target / "final-report.md")
    sensitivity = read_kv(target / "sensitivity.md")
    handoff = text(target / "99-handoff.md")
    method_reg = text(target / "method-registry.md")

    # BRIEF
    if brief.get("status", "").lower() != "frozen":
        rep.error("BRIEF: 00-brief.md status must be frozen")
    require_kv(brief, "brief_hash", rep, "00-brief.md")
    if not brief.get("brief_hash", "").startswith("sha256:"):
        rep.error("BRIEF: brief_hash must start with sha256:")
    if brief.get("open_blocking_questions", "") != "0":
        rep.error("BRIEF: open_blocking_questions must be 0")
    for key in ["approved_by", "approved_at", "approval_evidence", "amendment_policy", "freedom_profile", "model_class", "risk_class"]:
        require_kv(brief, key, rep, "00-brief.md")
    require_kv(task, "goal", rep, "task-spec.md")
    require_kv(task, "brief_hash", rep, "task-spec.md")
    require_kv(protocol, "protocol_registered_at", rep, "research-protocol.md")
    if "amendment_log" not in protocol:
        rep.error("research-protocol.md: amendment_log missing")

    # STATE / HANDOFF / CONTEXT
    require_kv(state, "task_id", rep, "00-state.md")
    require_kv(state, "freedom_profile", rep, "00-state.md")
    require_kv(state, "next_action", rep, "00-state.md")
    if "path:" not in text(target / "00-state.md") or "hash:" not in text(target / "00-state.md"):
        rep.error("CONTEXT_BUDGET: 00-state.md must reference loaded files by path+hash")
    for token in ["00-brief.md", "00-state.md", "task-spec.md", "research-protocol.md", "criteria.csv", "gates.json"]:
        if token not in handoff:
            rep.error(f"99-handoff.md: missing path {token}")
    require_kv(budget, "status", rep, "context-budget.md")
    if budget.get("status", "").lower() != "pass":
        rep.error("CONTEXT_BUDGET: context-budget status must be PASS")
    require_kv(deviation, "status", rep, "deviation-request.md", allow_dash=True)
    if state.get("freedom_profile", "").lower() == "frontier" and deviation.get("status", "").lower() not in {"none", "approved"}:
        rep.error("frontier profile requires deviation-request status none|approved")

    # Generic CSV field checks
    for filename, rows in data.items():
        for i, row in enumerate(rows, start=2):
            for field, allow_dash in CHECK_FIELDS.get(filename, []):
                if bad(row.get(field), allow_dash=allow_dash):
                    rep.error(f"{filename}:{i}: placeholder/empty '{field}'")

    candidates = data["candidates.csv"]
    adoption = data["adoption-evidence.csv"]
    features = data["feature-dictionary.csv"]
    evidence = data["feature-evidence.csv"]
    criteria = data["criteria.csv"]
    synthetic = data["synthetic-scores.csv"]
    gaps = data["gaps.csv"]
    matrix = data["decision-matrix.csv"]
    assignments = data["research-assignments.csv"]
    sources = data["sources.csv"]
    claims = data["claims.csv"]
    contradictions = data["contradictions.csv"]
    critiques = data["critique-log.csv"]
    compliance = data["compliance-matrix.csv"]

    cand_ids = {r.get("candidate_id", "") for r in candidates if r.get("candidate_id")}
    feat_ids = {r.get("feature_id", "") for r in features if r.get("feature_id")}
    crit_ids = {r.get("criterion_id", "") for r in criteria if r.get("criterion_id")}
    applies_all = {r.get("criterion_id", "") for r in criteria if r.get("applies_to_all", "").lower() == "yes"}
    synthetic_ids = {r.get("criterion_id", "") for r in criteria if r.get("synthetic", "").lower() == "yes"}

    # REUSE
    decision = reuse.get("decision", "").lower()
    if decision not in {"adopt", "adapt", "extend", "compose", "build"}:
        rep.error("REUSE_FIRST: reuse-decision decision invalid")
    require_kv(reuse, "reason", rep, "reuse-decision.md")
    require_kv(reuse, "proven_use_evidence", rep, "reuse-decision.md")
    require_kv(build, "build_selected", rep, "build-justification.md", allow_dash=True)
    require_kv(build, "gap_proven", rep, "build-justification.md", allow_dash=True)
    if decision == "build" and build.get("gap_proven", "").lower() != "yes":
        rep.error("BUILD_JUSTIFICATION: build requires gap_proven: yes")
    if not adoption:
        rep.error("CANDIDATE_ADOPTION: adoption-evidence.csv empty")
    for cid in cand_ids:
        if not any(r.get("candidate_id") == cid for r in adoption):
            rep.error(f"CANDIDATE_ADOPTION: no adoption evidence for {cid}")

    # CRITERIA
    valid_origins = {"brief", "domain_standard", "candidate_union", "synthetic"}
    valid_types = {"factual", "hard_gate", "weighted", "synthetic"}
    for i, row in enumerate(criteria, start=2):
        if row.get("origin", "").lower() not in valid_origins:
            rep.error(f"CRITERIA_TRANSPARENCY: criteria.csv:{i}: invalid origin")
        if row.get("type", "").lower() not in valid_types:
            rep.error(f"CRITERIA_TRANSPARENCY: criteria.csv:{i}: invalid type")
        if row.get("synthetic", "").lower() == "yes":
            if bad(row.get("formula"), allow_dash=False) or bad(row.get("input_feature_ids"), allow_dash=False):
                rep.error(f"SYNTHETIC_TRANSPARENCY: criteria.csv:{i}: synthetic criterion needs formula/inputs")
    for cid in synthetic_ids:
        if not any(r.get("criterion_id") == cid and r.get("sensitivity_status", "").lower() == "pass" for r in synthetic):
            rep.error(f"SYNTHETIC_TRANSPARENCY: no PASS sensitivity row for {cid}")

    # UNION / GAP FILLING / MATRIX COMPLETE
    ev_pairs = {(r.get("candidate_id", ""), r.get("feature_id", "")) for r in evidence}
    for cid in cand_ids:
        for fid in feat_ids:
            if (cid, fid) not in ev_pairs:
                rep.error(f"UNION_COMPLETE: missing feature-evidence cell {cid}/{fid}")
    for r in evidence:
        if r.get("status", "").lower() == "unknown":
            rep.error(f"GAP_FILLING: unknown feature cell {r.get('candidate_id')}/{r.get('feature_id')}")
    for r in gaps:
        if r.get("status", "").lower() in {"open", "unknown", "blocked"}:
            rep.error(f"GAP_FILLING: gap {r.get('gap_id')} is open")
    mat_pairs = {(r.get("candidate_id", ""), r.get("criterion_id", "")) for r in matrix}
    for cid in cand_ids:
        for kid in applies_all:
            if (cid, kid) not in mat_pairs:
                rep.error(f"MATRIX_COMPLETE: missing decision-matrix cell {cid}/{kid}")
    for r in matrix:
        if r.get("status", "").lower() == "unknown":
            rep.error(f"MATRIX_COMPLETE: unknown decision cell {r.get('candidate_id')}/{r.get('criterion_id')}")

    # ASSIGNMENTS / PROVENANCE / CRITIQUE
    if not assignments:
        rep.error("ASSIGNMENT: research-assignments.csv empty")
    for r in assignments:
        if r.get("status", "").lower() != "done":
            rep.error(f"ASSIGNMENT: assignment {r.get('assignment_id')} is not done")
    if not sources or not claims:
        rep.error("PROVENANCE: sources/claims empty")
    for r in claims:
        if r.get("decision_critical", "").lower() == "yes" and r.get("verification_status", "").lower() not in {"verified", "revised"}:
            rep.error(f"PROVENANCE: claim {r.get('claim_id')} not verified")
    if "M001" not in method_reg or "pre_registered_at" not in method_reg:
        rep.error("PROVENANCE: method-registry.md incomplete")
    for r in contradictions:
        if r.get("status", "").lower() in {"open", "unresolved-blocking"}:
            rep.error(f"CONTRADICTION: {r.get('contradiction_id')} unresolved")
    for r in critiques:
        if r.get("severity", "").lower() == "blocking" and r.get("status", "").lower() != "resolved":
            rep.error(f"CRITIQUE: {r.get('critique_id')} blocking unresolved")

    # SENSITIVITY / VERIFICATION / OUTPUT / HUMAN GATE
    if sensitivity.get("status", "").lower() != "pass" or sensitivity.get("winner_stability", "").lower() != "yes":
        rep.error("SENSITIVITY: sensitivity.md not PASS/stable")
    require_kv(sensitivity, "rank_reversal_at", rep, "sensitivity.md", allow_dash=True)
    if verification.get("status", "").lower() != "pass":
        rep.error("VERIFICATION: verification.md Status must be PASS")
    if final.get("status", "").lower() != "pass":
        rep.error("OUTPUT_CONTRACT: final-report.md Status must be PASS")
    require_kv(final, "decision", rep, "final-report.md")
    require_kv(final, "residual_unknowns", rep, "final-report.md", allow_dash=True)
    risk = state.get("risk_class", "").lower()
    if risk in {"high", "critical"}:
        if brief.get("human_gate", "").lower() != "yes" and "human_gate: yes" not in text(target / "verification.md"):
            rep.error("HUMAN_GATE: high risk requires human_gate: yes")
    for r in compliance:
        st = r.get("status", "").lower()
        if st == "missing":
            rep.error(f"OUTPUT_CONTRACT: compliance {r.get('standard_id')} missing")
        elif st == "partial":
            rep.warn(f"OUTPUT_CONTRACT: compliance {r.get('standard_id')} partial")
        try:
            if float(r.get("score", "0")) < 7:
                rep.warn(f"OUTPUT_CONTRACT: low compliance score {r.get('standard_id')}")
        except ValueError:
            rep.error(f"OUTPUT_CONTRACT: invalid score {r.get('standard_id')}")

    # NO FAKE PASS / RESIDUAL UNKNOWNS
    if "абсолютно полно" in text(target / "final-report.md").lower():
        rep.error("RESIDUAL_UNKNOWNS: absolute completeness claim forbidden")
    if not final.get("residual_unknowns") or bad(final.get("residual_unknowns"), allow_dash=True):
        rep.error("RESIDUAL_UNKNOWNS: final-report residual_unknowns missing")

    freedom = state.get("freedom_profile", "balanced").lower()
    if freedom not in {"frontier", "balanced", "regulated"}:
        freedom = "balanced"
    status = "PASS" if not rep.errors and not rep.warnings else "FAIL"
    gates = {
        "status": status,
        "task_dir": str(target),
        "errors": len(rep.errors),
        "warnings": len(rep.warnings),
        "gates_closed": GATES if status == "PASS" else [],
        "residual_unknowns": [final.get("residual_unknowns", "not set")],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "freedom_profile": freedom,
    }
    (target / "gates.json").write_text(json.dumps(gates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if rep.errors:
        for e in rep.errors[:40]:
            print("ERROR:", e)
    if rep.warnings:
        for w in rep.warnings[:20]:
            print("WARN:", w)
    print(f"{status}: {target}")
    print(f"errors={len(rep.errors)} warnings={len(rep.warnings)} freedom={freedom}")
    print(f"gates.json -> {target / 'gates.json'}")
    return 0 if status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="research/<task-id>")
    parser.add_argument("--init-v6", metavar="DIR", help="create v6 artifact tree")
    parser.add_argument("--force", action="store_true", help="overwrite non-empty init target")
    args = parser.parse_args()
    if args.init_v6:
        return init_v6(Path(args.init_v6), args.force)
    if not args.target:
        print("ERROR: provide target dir or --init-v6 DIR", file=sys.stderr)
        return 2
    return check_v6(Path(args.target))


if __name__ == "__main__":
    sys.exit(main())
