#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Deterministic score aggregator for skill-auditor (v3.0).
Features:
- Validates subagent/inline finding JSONs (criterion-level and streamlined dimension_score modes)
- Enforces Coverage Confidence (forbids CLEAR verdict when unreadable/binary files exist)
- Supports Policy Profiles (--policy strict | balanced | permissive)
- Computes Quick-Win ROI (+score gain per issue) deterministically
- Exports SARIF 2.1.0 (--sarif-out) for GitHub Code Scanning / IDE / CI
- Supports cross-round ledger & anti-regression diffing (--compare-prev) for bounded improve loops
- Renders Russian (default via config.json) or English Markdown summaries
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_DIMENSION_CATALOG: list[tuple[str, str, float]] = [
    ("D1", "Triggering & Discoverability", 14.0),
    ("D2", "Context Engineering & Progressive Disclosure", 16.0),
    ("D3", "Prompt & Procedural Engineering", 14.0),
    ("D4", "Multi-Agent, Sub-Skills & Orchestration", 16.0),
    ("D5", "Tools, MCP Integration & External Resources", 12.0),
    ("D6", "Verification, Guardrails & Reliability", 12.0),
    ("D7", "Security, Trust Boundaries & Supply-Chain Safety", 10.0),
    ("D8", "Cross-Platform Portability & Maintainability", 6.0),
]
DIMENSION_CATALOG = DEFAULT_DIMENSION_CATALOG

POLICY_PROFILES = ("strict", "balanced", "permissive")

RATING_RU: dict[str, str] = {
    "Exemplary": "Эталонно (Exemplary)",
    "Strong": "Сильно (Strong)",
    "Adequate": "Приемлемо (Adequate)",
    "Weak": "Слабо (Weak)",
    "Critical": "Критично (Critical)",
    "N/A": "N/A",
}


def load_skill_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load skill-auditor/config.json if available, else return safe defaults."""
    target = config_path or (Path(__file__).resolve().parent.parent / "config.json")
    defaults: dict[str, Any] = {
        "default_output_language": "ru",
        "default_policy_profile": "balanced",
        "dimension_weights": {},
        "custom_dimensions": [],
    }
    if not target.exists():
        return defaults
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            defaults.update(loaded)
    except Exception:  # noqa: BLE001
        pass
    return defaults


def resolve_dimension_catalog(config: dict[str, Any] | None = None) -> list[tuple[str, str, float]]:
    """Build active dimension catalog from defaults + optional config.json overrides/custom_dimensions."""
    cfg = config or {}
    weights_override = cfg.get("dimension_weights") or {}
    custom_dims = cfg.get("custom_dimensions") or []

    catalog: list[tuple[str, str, float]] = []
    seen_ids: set[str] = set()
    for dim_id, dim_name, base_w in DEFAULT_DIMENSION_CATALOG:
        w = float(weights_override.get(dim_id, base_w))
        if w < 0:
            raise ValueError(f"Negative weight for dimension '{dim_id}': {w}")
        if w > 0:
            catalog.append((dim_id, dim_name, w))
            seen_ids.add(dim_id)

    for item in custom_dims:
        cid = str(item.get("id", "")).strip()
        cname = str(item.get("name", cid)).strip()
        cw = float(item.get("weight", 0.0))
        if not cid or cw <= 0:
            raise ValueError(f"Invalid custom dimension entry in config.json: {item}")
        if cid in seen_ids:
            raise ValueError(f"Duplicate custom dimension id '{cid}' in config.json")
        catalog.append((cid, cname, cw))
        seen_ids.add(cid)

    total_w = round(sum(w for _, _, w in catalog), 4)
    if abs(total_w - 100.0) > 0.01:
        raise ValueError(f"Dimension weights in config.json must sum to 100.0 (got {total_w}).")
    return catalog


def grade_for_score(score: float) -> str:
    if score >= 90.0:
        return "A"
    if score >= 75.0:
        return "B"
    if score >= 60.0:
        return "C"
    if score >= 40.0:
        return "D"
    return "F"


def rating_for_ratio(ratio: float) -> str:
    if ratio >= 0.90:
        return "Exemplary"
    if ratio >= 0.75:
        return "Strong"
    if ratio >= 0.60:
        return "Adequate"
    if ratio >= 0.40:
        return "Weak"
    return "Critical"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON in '{path}': {exc}") from exc


def _compute_roi_actions(
    breakdown: list[dict[str, Any]],
    all_issues: list[dict[str, Any]],
    veto_flags: list[dict[str, Any]],
    uncapped_total: float,
    final_score: float,
) -> list[dict[str, Any]]:
    """Estimate deterministic score gain (+points) per issue using dimension headroom and priority weight."""
    dim_headroom: dict[str, float] = {}
    dim_weight_sum: dict[str, float] = {}
    prio_weight = {"P0": 3.0, "P1": 2.0, "P2": 1.0}

    for d in breakdown:
        if d["applicable"]:
            dim_headroom[d["dimension_id"]] = max(0.0, round(d["weight_effective"] - d["weighted_points"], 2))
            dim_weight_sum[d["dimension_id"]] = 0.0

    for iss in all_issues:
        did = str(iss.get("dimension_id", ""))
        pw = prio_weight.get(str(iss.get("priority", "P2")).upper(), 1.0)
        if did in dim_weight_sum:
            dim_weight_sum[did] += pw

    gate_unlock_pool = max(0.0, round(uncapped_total - final_score, 1))
    roi_rows: list[dict[str, Any]] = []

    for iss in all_issues:
        did = str(iss.get("dimension_id", ""))
        prio = str(iss.get("priority", "P2")).upper()
        pw = prio_weight.get(prio, 1.0)
        denom = dim_weight_sum.get(did, 0.0) or pw
        room = dim_headroom.get(did, 0.0)
        est_gain = round(room * (pw / denom), 2)
        unlock_note = None
        if gate_unlock_pool > 0 and did == "D7" and prio == "P0":
            unlock_note = f"+{gate_unlock_pool} gate unlock"
        roi_rows.append(
            {
                "id": iss.get("id", f"{did}-issue"),
                "priority": prio,
                "dimension_id": did,
                "location": iss.get("location", ""),
                "title": iss.get("title", iss.get("smell_code", "Improve criterion")),
                "estimated_score_gain": est_gain,
                "gate_unlock_potential": gate_unlock_pool if unlock_note else 0.0,
                "roi_sort_key": est_gain + (gate_unlock_pool if unlock_note else 0.0),
            }
        )

    if gate_unlock_pool > 0 and not any(r["gate_unlock_potential"] > 0 for r in roi_rows):
        for vf in veto_flags[:3]:
            roi_rows.append(
                {
                    "id": vf.get("rule_id", "SEC-GATE"),
                    "priority": "P0",
                    "dimension_id": "D7",
                    "location": vf.get("location", ""),
                    "title": f"Resolve {vf.get('gate_level', 'HIGH')} security gate ({vf.get('rule_id', '')})",
                    "estimated_score_gain": 0.0,
                    "gate_unlock_potential": gate_unlock_pool,
                    "roi_sort_key": gate_unlock_pool,
                }
            )

    roi_rows.sort(key=lambda r: (r["roi_sort_key"], 3 if r["priority"] == "P0" else (2 if r["priority"] == "P1" else 1)), reverse=True)
    return roi_rows[:7]


def compare_with_previous(current: dict[str, Any], prev: dict[str, Any]) -> dict[str, Any]:
    """Cross-round findings ledger & anti-guarantee-weakening comparison for bounded improve loops."""
    def _issue_keys(summary: dict[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        pa = summary.get("prioritized_actions") or {}
        for bucket in ("P0_blockers", "P1_high_impact", "P2_polish"):
            for item in pa.get(bucket, []):
                k = f"{item.get('dimension_id', '')}:{item.get('smell_code') or item.get('id') or item.get('title', '')}"
                out[k] = str(item.get("title", k))
        return out

    curr_score = float(current.get("final_score", 0.0))
    prev_score = float(prev.get("final_score", 0.0))
    delta = round(curr_score - prev_score, 1)

    curr_map = _issue_keys(current)
    prev_map = _issue_keys(prev)
    resolved = sorted(v for k, v in prev_map.items() if k not in curr_map)
    remaining = sorted(v for k, v in curr_map.items() if k in prev_map)
    introduced = sorted(v for k, v in curr_map.items() if k not in prev_map)

    pa_curr = current.get("prioritized_actions") or {}
    open_p0_p1 = len(pa_curr.get("P0_blockers", [])) + len(pa_curr.get("P1_high_impact", []))
    converged = open_p0_p1 == 0 and current.get("security_gate") == "CLEAR"

    # Mechanical anti-guarantee-weakening signal: security/verification regression or lost coverage
    dim_curr = {d["dimension_id"]: d for d in current.get("dimension_breakdown", []) if d.get("applicable")}
    dim_prev = {d["dimension_id"]: d for d in prev.get("dimension_breakdown", []) if d.get("applicable")}
    weakening_alerts: list[str] = []
    for guarded_dim in ("D6", "D7"):
        if guarded_dim in dim_curr and guarded_dim in dim_prev:
            r_curr = float(dim_curr[guarded_dim].get("raw_ratio") or 0.0)
            r_prev = float(dim_prev[guarded_dim].get("raw_ratio") or 0.0)
            if r_curr < r_prev - 0.05:
                weakening_alerts.append(
                    f"Dimension {guarded_dim} ratio dropped from {round(r_prev * 100)}% to {round(r_curr * 100)}% (possible guarantee weakening or verification shortcut)."
                )
    if prev.get("coverage_status") == "COMPLETE" and current.get("coverage_status") != "COMPLETE":
        weakening_alerts.append("File coverage degraded from COMPLETE to INCOMPLETE between rounds.")

    return {
        "previous_score": prev_score,
        "current_score": curr_score,
        "score_delta": delta,
        "resolved_issues_count": len(resolved),
        "resolved_issues": resolved,
        "remaining_issues_count": len(remaining),
        "newly_introduced_issues": introduced,
        "converged": converged,
        "non_convergence_warning": (not converged and delta <= 0.0),
        "guarantee_weakening_alerts": weakening_alerts,
    }


def aggregate(
    static_report: dict[str, Any],
    finding_docs: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    output_language: str | None = None,
    policy_profile: str | None = None,
) -> dict[str, Any]:
    cfg = config if config is not None else load_skill_config()
    lang = (output_language or str(cfg.get("default_output_language", "ru"))).strip().lower() or "ru"
    policy = (policy_profile or str(cfg.get("default_policy_profile", "balanced"))).strip().lower() or "balanced"
    if policy not in POLICY_PROFILES:
        raise ValueError(f"Unsupported policy profile '{policy}'. Must be one of {POLICY_PROFILES}.")

    dim_catalog = resolve_dimension_catalog(cfg)
    dim_assessments: dict[str, dict[str, Any]] = {}
    veto_flags: list[dict[str, Any]] = []
    cleared_list: list[dict[str, str]] = []
    cleared_keys: set[tuple[str, str]] = set()
    beyond_insights: list[str] = []
    cross_notes: list[str] = []
    script_reviews: list[dict[str, Any]] = []

    for doc in finding_docs:
        for da in doc.get("dimension_assessments", []):
            dim_id = da.get("dimension_id")
            if not dim_id:
                continue
            if dim_id in dim_assessments:
                raise ValueError(
                    f"Duplicate assessment for dimension '{dim_id}' across finding files."
                )
            dim_assessments[dim_id] = da

        for cf in doc.get("cleared_static_findings", []):
            rule_id = str(cf.get("rule_id", "")).strip()
            location = str(cf.get("location", "")).strip()
            reason = str(cf.get("reason", "")).strip()
            if not (rule_id and location and reason):
                raise ValueError(
                    "Each cleared_static_findings entry must specify non-empty rule_id, location, and reason."
                )
            cleared_keys.add((rule_id, location))
            cleared_list.append({"rule_id": rule_id, "location": location, "reason": reason})

        for vf in doc.get("security_veto_flags", []):
            veto_flags.append(vf)
        for sr in doc.get("script_rationality_reviews", []):
            if isinstance(sr, dict) and sr.get("file"):
                script_reviews.append(sr)
        for insight in doc.get("beyond_rubric_insights", []):
            if insight and str(insight) not in beyond_insights:
                beyond_insights.append(str(insight))
        for note in doc.get("cross_agent_conflicts_or_notes", []):
            if note:
                cross_notes.append(str(note))

    for sf in static_report.get("security_findings", []):
        sev = str(sf.get("severity", "")).upper()
        if sev in {"CRITICAL", "HIGH"}:
            rule_id = str(sf.get("rule_id", "SEC-STATIC"))
            location = f"{sf.get('file', 'unknown')}:{sf.get('line', 0)}"
            if (rule_id, location) in cleared_keys:
                continue
            veto_flags.append(
                {
                    "gate_level": sev,
                    "rule_id": rule_id,
                    "location": location,
                    "evidence": sf.get("snippet", ""),
                    "cap_score_at": 39 if sev == "CRITICAL" else 69,
                    "required_action": sf.get("remediation", "Remediate static security finding."),
                }
            )

    missing_dims = [d[0] for d in dim_catalog if d[0] not in dim_assessments]
    if missing_dims:
        raise ValueError(f"Missing dimension assessments for: {', '.join(missing_dims)}")

    active_base_weight = 0.0
    for dim_id, _, base_w in dim_catalog:
        da = dim_assessments[dim_id]
        if da.get("applicable", True):
            active_base_weight += base_w

    if active_base_weight <= 0:
        raise ValueError("No applicable dimensions found to score.")

    breakdown: list[dict[str, Any]] = []
    uncapped_total = 0.0
    p0_issues: list[dict[str, Any]] = []
    p1_issues: list[dict[str, Any]] = []
    p2_issues: list[dict[str, Any]] = []
    all_issues_flat: list[dict[str, Any]] = []
    smells_seen: set[str] = {
        s.get("code", "")
        for s in static_report.get("static_smells", [])
        if s.get("code") and s.get("severity") != "recommendation"
    }

    for dim_id, dim_name, base_w in dim_catalog:
        da = dim_assessments[dim_id]
        applicable = bool(da.get("applicable", True))
        if not applicable:
            breakdown.append(
                {
                    "dimension_id": dim_id,
                    "name": dim_name,
                    "weight_base": base_w,
                    "weight_effective": 0.0,
                    "applicable": False,
                    "na_reason": da.get("na_reason", "Not applicable for this target."),
                    "raw_ratio": None,
                    "weighted_points": 0.0,
                    "rating": "N/A",
                    "summary": da.get("dimension_summary", ""),
                }
            )
            continue

        effective_w = round((base_w / active_base_weight) * 100.0, 2)
        c_scores = da.get("criterion_scores")

        if isinstance(c_scores, list) and len(c_scores) > 0:
            got = 0.0
            mx = 0.0
            for c in c_scores:
                sc = float(c.get("score", 0))
                cmx = float(c.get("max_score", 5))
                if cmx <= 0 or sc < 0 or sc > cmx:
                    raise ValueError(
                        f"Invalid score {sc}/{cmx} in {dim_id} criterion {c.get('criterion_id', '')}: must be within [0, max_score]."
                    )
                got += sc
                mx += cmx
            issue_sources = c_scores
        elif da.get("dimension_score") is not None:
            got = float(da["dimension_score"])
            mx = float(da.get("dimension_max", 5.0))
            if mx <= 0 or got < 0 or got > mx:
                raise ValueError(
                    f"Invalid dimension_score {got}/{mx} in {dim_id}: must be within [0, dimension_max]."
                )
            issue_sources = [{"criterion_id": dim_id, "issues": da.get("issues", [])}]
        else:
            raise ValueError(
                f"Dimension {dim_id} is applicable=true but has neither criterion_scores nor dimension_score."
            )

        ratio = (got / mx) if mx > 0 else 0.0
        weighted_pts = round(ratio * effective_w, 2)
        uncapped_total += ratio * (base_w / active_base_weight) * 100.0

        for src in issue_sources:
            for issue in src.get("issues", []):
                smell = issue.get("smell_code")
                if smell:
                    smells_seen.add(str(smell))
                prio = str(issue.get("priority", "P2")).upper()
                enriched = dict(issue)
                enriched.setdefault("dimension_id", dim_id)
                enriched.setdefault("criterion_id", src.get("criterion_id", dim_id))
                all_issues_flat.append(enriched)
                if prio == "P0":
                    p0_issues.append(enriched)
                elif prio == "P1":
                    p1_issues.append(enriched)
                else:
                    p2_issues.append(enriched)

        breakdown.append(
            {
                "dimension_id": dim_id,
                "name": dim_name,
                "weight_base": base_w,
                "weight_effective": effective_w,
                "applicable": True,
                "raw_score": round(got, 2),
                "raw_max": round(mx, 2),
                "raw_ratio": round(ratio, 4),
                "weighted_points": weighted_pts,
                "rating": rating_for_ratio(ratio),
                "summary": da.get("dimension_summary", ""),
            }
        )

    uncapped_total = round(min(100.0, uncapped_total), 1)

    dedup_vetos: list[dict[str, Any]] = []
    seen_veto_keys: set[tuple[str, str, str]] = set()
    for vf in veto_flags:
        k = (
            str(vf.get("gate_level", "")).upper(),
            str(vf.get("rule_id", "")),
            str(vf.get("location", "")),
        )
        if k not in seen_veto_keys:
            seen_veto_keys.add(k)
            dedup_vetos.append(vf)

    has_critical_veto = any(str(v.get("gate_level", "")).upper() == "CRITICAL" for v in dedup_vetos)
    has_high_veto = any(str(v.get("gate_level", "")).upper() == "HIGH" for v in dedup_vetos)
    core_spec_fail = static_report.get("platform_compatibility", {}).get("agentskills_core") == "FAIL"

    coverage_info = static_report.get("coverage") or {"complete": True, "unreadable_or_binary_files": []}
    coverage_complete = bool(coverage_info.get("complete", True))
    coverage_status = "COMPLETE" if coverage_complete else "INCOMPLETE_COVERAGE"

    has_static_error = any(
        s.get("severity") in {"error", "critical"}
        for s in static_report.get("static_smells", [])
    )

    final_score = uncapped_total
    security_gate = "CLEAR"
    if has_critical_veto:
        final_score = min(final_score, 39.0)
        security_gate = "BLOCKED_CRITICAL"
    elif has_high_veto and policy in {"strict", "balanced"}:
        final_score = min(final_score, 69.0)
        security_gate = "CAPPED_HIGH"
    elif not coverage_complete:
        security_gate = "INCOMPLETE_COVERAGE"
        final_score = min(final_score, 74.0 if policy == "strict" else 89.0)
    elif policy == "strict" and has_static_error:
        final_score = min(final_score, 74.0)

    if core_spec_fail:
        final_score = min(final_score, 59.0)

    final_score = round(final_score, 1)
    grade = grade_for_score(final_score)

    if security_gate == "BLOCKED_CRITICAL" or grade == "F":
        verdict = "BLOCKED_REMEDIATE_CRITICAL_ISSUES"
    elif core_spec_fail or grade == "D" or security_gate == "CAPPED_HIGH":
        verdict = "NEEDS_REFACTORING_BEFORE_USE"
    elif security_gate == "INCOMPLETE_COVERAGE":
        verdict = "MANUAL_REVIEW_REQUIRED_INCOMPLETE_COVERAGE"
    elif grade == "C":
        verdict = "CONDITIONAL_PASS_IMPROVE_RELIABILITY"
    elif grade == "B":
        verdict = "PASS_WITH_RECOMMENDATIONS"
    else:
        verdict = "PRODUCTION_READY"

    roi_actions = _compute_roi_actions(breakdown, all_issues_flat, dedup_vetos, uncapped_total, final_score)

    return {
        "schema_version": "3.1.0",
        "output_language": lang,
        "policy_profile": policy,
        "skill_name": static_report.get("skill_name", "unknown"),
        "target_type": static_report.get("target_type", "skill-package"),
        "target_path": static_report.get("target_path", ""),
        "skill_tier": static_report.get("tier_classification", {}).get("detected_tier", "Unknown"),
        "final_score": final_score,
        "uncapped_score": uncapped_total,
        "grade": grade,
        "verdict": verdict,
        "security_gate": security_gate,
        "coverage_status": coverage_status,
        "unreadable_or_binary_files": coverage_info.get("unreadable_or_binary_files", []),
        "token_budget": (static_report.get("inventory") or {}).get("token_budget", {}),
        "security_veto_flags": dedup_vetos,
        "cleared_static_findings": cleared_list,
        "platform_compatibility": static_report.get("platform_compatibility", {}),
        "dimension_breakdown": breakdown,
        "script_rationality_reviews": script_reviews,
        "top_smells_detected": sorted(smells_seen),
        "prioritized_actions": {
            "P0_blockers": p0_issues,
            "P1_high_impact": p1_issues,
            "P2_polish": p2_issues,
        },
        "roi_top_actions": roi_actions,
        "beyond_rubric_insights": beyond_insights,
        "cross_agent_notes": cross_notes,
    }


def _parse_location(raw: str) -> tuple[str, int]:
    if ":" in raw:
        uri, _, line_str = raw.rpartition(":")
        m = re.match(r"(\d+)", line_str.strip())
        if m and uri:
            return uri.strip(), max(1, int(m.group(1)))
    return (raw.strip() or "SKILL.md"), 1


def to_sarif(static_report: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Generate a SARIF 2.1.0 report for GitHub Code Scanning / CI / IDE integration."""
    rules_map: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    def _add_result(rule_id: str, level: str, message: str, loc_str: str) -> None:
        if rule_id not in rules_map:
            rules_map[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
            }
        uri, line = _parse_location(loc_str)
        results.append(
            {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {"startLine": line},
                        }
                    }
                ],
            }
        )

    for vf in summary.get("security_veto_flags", []):
        lvl = "error" if str(vf.get("gate_level", "")).upper() in {"CRITICAL", "HIGH"} else "warning"
        _add_result(
            str(vf.get("rule_id", "SEC-GATE")),
            lvl,
            f"[{vf.get('gate_level', 'HIGH')}] {vf.get('required_action', vf.get('evidence', 'Security violation'))}",
            str(vf.get("location", "SKILL.md:1")),
        )

    for sm in static_report.get("static_smells", []):
        sev = str(sm.get("severity", "warning")).lower()
        if sev == "recommendation":
            continue
        lvl = "error" if sev in {"critical", "error"} else "warning"
        _add_result(
            str(sm.get("code", "STATIC-SMELL")),
            lvl,
            str(sm.get("message", "")),
            str(sm.get("file", "SKILL.md")),
        )

    pa = summary.get("prioritized_actions") or {}
    for bucket, lvl in (("P0_blockers", "error"), ("P1_high_impact", "warning")):
        for iss in pa.get(bucket, []):
            rid = str(iss.get("smell_code") or iss.get("criterion_id") or iss.get("id") or "AUDIT-ISSUE")
            msg = f"{iss.get('title', rid)}: {iss.get('fix_suggestion', iss.get('impact', ''))}".strip()
            _add_result(rid, lvl, msg, str(iss.get("location", "SKILL.md:1")))

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skill-auditor",
                        "version": "3.1.0",
                        "rules": list(rules_map.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def render_markdown_summary(
    summary: dict[str, Any],
    lang: str | None = None,
    round_diff: dict[str, Any] | None = None,
) -> str:
    out_lang = (lang or str(summary.get("output_language", "ru"))).strip().lower()
    is_ru = out_lang.startswith("ru")

    tb = summary.get("token_budget") or {}
    tb_str = (
        f"SKILL.md `{tb.get('skill_md_tokens', '?')}` tok · всего пакет `{tb.get('total_package_tokens', '?')}` tok ({tb.get('pct_of_200k_window', '?')}% от 200K)"
        if tb
        else "—"
    )
    pc = summary.get("platform_compatibility") or {}
    up = pc.get("universal_portability") or {}
    if up:
        port_ru = (
            f"**{up.get('portability_score_pct', '?')}%** ({up.get('format_ready_count', '?')}/{up.get('total_targets', 17)} PASS, "
            f"{up.get('format_warn_count', 0)} WARN, {up.get('format_fail_count', 0)} FAIL · скоуп: `{up.get('detected_install_scope', 'unknown')}`)"
        )
        port_en = (
            f"**{up.get('portability_score_pct', '?')}%** ({up.get('format_ready_count', '?')}/{up.get('total_targets', 17)} PASS, "
            f"{up.get('format_warn_count', 0)} WARN, {up.get('format_fail_count', 0)} FAIL · scope: `{up.get('detected_install_scope', 'unknown')}`)"
        )
    else:
        port_ru = f"Core `{pc.get('agentskills_core', '?')}` · Claude `{pc.get('claude_code', '?')}` · Codex `{pc.get('openai_codex', '?')}` · Cursor `{pc.get('cursor', '?')}`"
        port_en = port_ru

    if is_ru:
        lines = [
            f"# Сводка аудита скила: `{summary['skill_name']}`",
            "",
            f"- **Тип / Уровень:** `{summary.get('target_type', 'skill-package')}` · {summary['skill_tier']}",
            f"- **Итоговый балл:** **{summary['final_score']} / 100** (Грейд **{summary['grade']}**, без капов: {summary['uncapped_score']})",
            f"- **Вердикт / Политика:** `{summary['verdict']}` (профиль: `{summary.get('policy_profile', 'balanced')}`)",
            f"- **Security Gate & Покрытие:** `{summary['security_gate']}` · Покрытие: `{summary.get('coverage_status', 'COMPLETE')}`",
            f"- **Кросс-агентная переносимость:** {port_ru}",
            f"- **Бюджет токенов пакета:** {tb_str}",
            "",
            "## Разбивка по измерениям",
            "",
            "| ID | Измерение | Эфф. вес | Доля | Баллы | Рейтинг |",
            "|---|---|---:|---:|---:|---|",
        ]
        for d in summary["dimension_breakdown"]:
            if not d["applicable"]:
                lines.append(f"| {d['dimension_id']} | {d['name']} | 0% (N/A) | — | — | N/A |")
            else:
                pct = f"{round(d['raw_ratio'] * 100)}%"
                rating_lbl = RATING_RU.get(d["rating"], d["rating"])
                lines.append(
                    f"| {d['dimension_id']} | {d['name']} | {d['weight_effective']}% | {pct} | {d['weighted_points']} | {rating_lbl} |"
                )
        if pc.get("agents"):
            flagged = [
                f"`{info.get('display_name', aid)}` ({info.get('format_status')})"
                for aid, info in pc["agents"].items()
                if info.get("format_status") in {"WARN", "FAIL"}
            ]
            if flagged:
                lines.extend(["", f"**Агенты с предупреждениями/ошибками формата:** {', '.join(flagged[:12])}"])
        if summary.get("roi_top_actions"):
            lines.extend(["", "## Топ-улучшения по ROI (оценка прироста балла)", "", "| Приор. | Локация | Задача | Оценка прироста |", "|---|---|---|---|"])
            for r in summary["roi_top_actions"][:5]:
                gain = f"+{r['estimated_score_gain']} б."
                if r.get("gate_unlock_potential", 0) > 0:
                    gain += f" (+{r['gate_unlock_potential']} снятие гейта)"
                lines.append(f"| {r['priority']} | `{r['location'] or r['dimension_id']}` | {r['title']} | {gain} |")
        if summary["security_veto_flags"]:
            lines.extend(["", "## Сработавшие Security Hard Gates", ""])
            for v in summary["security_veto_flags"]:
                lines.append(f"- **[{v['gate_level']}] {v['rule_id']}** в `{v['location']}` — {v['required_action']}")
        if summary.get("cleared_static_findings"):
            lines.extend(["", "## Снятые ложные срабатывания статики", ""])
            for c in summary["cleared_static_findings"]:
                lines.append(f"- `{c['rule_id']}` в `{c['location']}` — {c['reason']}")
        if round_diff:
            lines.extend([
                "",
                "## Журнал раунда улучшения (Cross-Round Ledger)",
                "",
                f"- **Дельта балла:** `{round_diff['previous_score']} -> {round_diff['current_score']}` (`{round_diff['score_delta']:+}`)",
                f"- **Закрыто / Осталось / Новые:** `{round_diff['resolved_issues_count']}` / `{round_diff['remaining_issues_count']}` / `{len(round_diff['newly_introduced_issues'])}` · Сходимость: `{round_diff['converged']}`",
            ])
            if round_diff["guarantee_weakening_alerts"]:
                lines.append(f"- **ТРЕВОГА (Guarantee Weakening):** {'; '.join(round_diff['guarantee_weakening_alerts'])}")
        if summary["top_smells_detected"]:
            lines.extend(["", f"**Выявленные запахи / коды сбоев:** {', '.join(summary['top_smells_detected'])}"])
        return "\n".join(lines) + "\n"

    lines = [
        f"# Skill Audit Summary: `{summary['skill_name']}`",
        "",
        f"- **Type / Tier:** `{summary.get('target_type', 'skill-package')}` · {summary['skill_tier']}",
        f"- **Score:** **{summary['final_score']} / 100** (Grade **{summary['grade']}**, uncapped: {summary['uncapped_score']})",
        f"- **Verdict / Policy:** `{summary['verdict']}` (`{summary.get('policy_profile', 'balanced')}`)",
        f"- **Security Gate & Coverage:** `{summary['security_gate']}` · Coverage: `{summary.get('coverage_status', 'COMPLETE')}`",
        f"- **Cross-Agent Portability:** {port_en}",
        f"- **Token Budget:** {tb_str}",
        "",
        "## Dimension Breakdown",
        "",
        "| Dim | Dimension | Effective Weight | Ratio | Points | Rating |",
        "|---|---|---:|---:|---:|---|",
    ]
    for d in summary["dimension_breakdown"]:
        if not d["applicable"]:
            lines.append(f"| {d['dimension_id']} | {d['name']} | 0% (N/A) | — | — | N/A |")
        else:
            pct = f"{round(d['raw_ratio'] * 100)}%"
            lines.append(
                f"| {d['dimension_id']} | {d['name']} | {d['weight_effective']}% | {pct} | {d['weighted_points']} | {d['rating']} |"
            )
    if pc.get("agents"):
        flagged = [
            f"`{info.get('display_name', aid)}` ({info.get('format_status')})"
            for aid, info in pc["agents"].items()
            if info.get("format_status") in {"WARN", "FAIL"}
        ]
        if flagged:
            lines.extend(["", f"**Agents with format warnings/failures:** {', '.join(flagged[:12])}"])
    if summary.get("roi_top_actions"):
        lines.extend(["", "## Top Quick-Win ROI Actions", "", "| Prio | Location | Action | Est. Gain |", "|---|---|---|---|"])
        for r in summary["roi_top_actions"][:5]:
            gain = f"+{r['estimated_score_gain']} pts"
            if r.get("gate_unlock_potential", 0) > 0:
                gain += f" (+{r['gate_unlock_potential']} gate unlock)"
            lines.append(f"| {r['priority']} | `{r['location'] or r['dimension_id']}` | {r['title']} | {gain} |")
    if summary["security_veto_flags"]:
        lines.extend(["", "## Security Hard Gate Flags", ""])
        for v in summary["security_veto_flags"]:
            lines.append(f"- **[{v['gate_level']}] {v['rule_id']}** at `{v['location']}` — {v['required_action']}")
    if summary.get("cleared_static_findings"):
        lines.extend(["", "## Cleared Static Security False Positives", ""])
        for c in summary["cleared_static_findings"]:
            lines.append(f"- `{c['rule_id']}` at `{c['location']}` — {c['reason']}")
    if round_diff:
        lines.extend([
            "",
            "## Improve-Loop Round Ledger",
            "",
            f"- **Score Delta:** `{round_diff['previous_score']} -> {round_diff['current_score']}` (`{round_diff['score_delta']:+}`)",
            f"- **Resolved / Remaining / New:** `{round_diff['resolved_issues_count']}` / `{round_diff['remaining_issues_count']}` / `{len(round_diff['newly_introduced_issues'])}` · Converged: `{round_diff['converged']}`",
        ])
    if summary["top_smells_detected"]:
        lines.extend(["", f"**Detected Smells / Failure Codes:** {', '.join(summary['top_smells_detected'])}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate static audit + evaluator finding JSONs into final skill score, ROI ranking, and SARIF.",
        epilog="Exit codes: 0 = aggregation complete, 1 = invalid arguments/schema error, 2 = failed CI gate with --fail-on-gate.",
    )
    parser.add_argument("--static", required=True, help="Path to static_audit.json")
    parser.add_argument(
        "--findings",
        nargs="+",
        required=True,
        help="Paths to finding JSON files (or directories containing finding_*.json)",
    )
    parser.add_argument("--output", "-o", default="-", help="Output JSON path (default: stdout)")
    parser.add_argument("--markdown-out", help="Optional path to write rendered Markdown summary table")
    parser.add_argument("--sarif-out", help="Optional path to write SARIF 2.1.0 output for GitHub/IDE CI")
    parser.add_argument("--compare-prev", help="Optional previous audit_summary.json to compute cross-round improve ledger")
    parser.add_argument("--config", help="Optional path to skill config.json (default: ../config.json)")
    parser.add_argument("--lang", help="Override output language (e.g., ru, en; default from config.json)")
    parser.add_argument("--policy", choices=POLICY_PROFILES, help="Override policy profile (strict, balanced, permissive)")
    parser.add_argument("--fail-on-gate", action="store_true", help="Exit 2 if Security/Spec gate fails under active policy")

    args = parser.parse_args()
    static_path = Path(args.static)
    if not static_path.exists():
        print(f"Error: static report not found: {static_path}", file=sys.stderr)
        return 1

    finding_paths: list[Path] = []
    for raw_p in args.findings:
        p = Path(raw_p)
        if not p.exists():
            print(f"Error: finding path does not exist: {p}", file=sys.stderr)
            return 1
        if p.is_dir():
            finding_paths.extend(sorted(p.glob("finding_*.json")))
        else:
            finding_paths.append(p)

    if not finding_paths:
        print("Error: no finding JSON files found.", file=sys.stderr)
        return 1

    try:
        cfg = load_skill_config(Path(args.config) if args.config else None)
        static_report = load_json(static_path)
        finding_docs = [load_json(fp) for fp in finding_paths]
        summary = aggregate(
            static_report,
            finding_docs,
            config=cfg,
            output_language=args.lang,
            policy_profile=args.policy,
        )
        round_diff: dict[str, Any] | None = None
        if args.compare_prev:
            prev_summary = load_json(Path(args.compare_prev))
            round_diff = compare_with_previous(summary, prev_summary)
            summary["round_comparison"] = round_diff
    except Exception as exc:  # noqa: BLE001
        print(f"Error aggregating audit findings: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(rendered)
    else:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(rendered + "\n", encoding="utf-8")
        print(f"Aggregated audit JSON written to {out_p}", file=sys.stderr)

    if args.markdown_out:
        md_p = Path(args.markdown_out)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        md_p.write_text(render_markdown_summary(summary, round_diff=round_diff), encoding="utf-8")
        print(f"Markdown summary written to {md_p}", file=sys.stderr)

    if args.sarif_out:
        sarif_p = Path(args.sarif_out)
        sarif_p.parent.mkdir(parents=True, exist_ok=True)
        sarif_doc = to_sarif(static_report, summary)
        sarif_p.write_text(json.dumps(sarif_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"SARIF 2.1.0 written to {sarif_p}", file=sys.stderr)

    if args.fail_on_gate:
        gate = summary["security_gate"]
        core_fail = summary.get("platform_compatibility", {}).get("agentskills_core") == "FAIL"
        if gate in {"BLOCKED_CRITICAL", "CAPPED_HIGH"} or core_fail or (
            summary["policy_profile"] == "strict" and gate == "INCOMPLETE_COVERAGE"
        ):
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
