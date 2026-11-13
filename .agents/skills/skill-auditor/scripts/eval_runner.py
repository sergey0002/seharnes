#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Deterministic Smart A/B & Runtime Execution Evaluator helper for skill-auditor (v3.0).

Key principles:
- Zero semantic regex heuristics (AI/execution-evaluator determines AB_MEANINGFUL vs
  WITH_SKILL_ONLY vs HYBRID applicability and grades trace adherence).
- Avoids meaningless A/B tests on skills providing unique deterministic validation,
  private schemas, or custom scripts impossible without the skill (marks them
  WITH_SKILL_ONLY and evaluates runtime execution trace deeply).
- Computes Four Buckets (WORKING / GAP / REDUNDANT / REGRESSION) + Runtime Buckets
  (RUNTIME_PASS / RUNTIME_GAP), honest Impact Score (only over AB_MEANINGFUL cases),
  and 5-axis Runtime Execution Score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

APPLICABILITY_MODES = ("AB_MEANINGFUL", "WITH_SKILL_ONLY", "HYBRID")

RUNTIME_AXES: list[tuple[str, str, str]] = [
    ("progressive_disclosure", "Progressive Disclosure Adherence", "Соблюдение прогрессивного раскрытия (загрузка только нужных ссылок)"),
    ("script_and_tool_discipline", "Script & Tool Discipline", "Дисциплина скриптов и инструментов (без галлюцинаций, обработка stderr)"),
    ("invariant_and_guardrail_compliance", "Invariant & Guardrail Compliance", "Соблюдение инвариантов, HITL и границ недоверия без срезания углов"),
    ("context_and_turn_economy", "Context & Turn Economy", "Экономия контекста и ходов (отсутствие петель и лишних чтений)"),
    ("output_spec_accuracy", "Output & Spec Accuracy", "Точность соответствия строгой схеме/контракту результата"),
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON in '{path}': {exc}") from exc


def load_default_language(config_path: Path | None = None) -> str:
    cfg_p = config_path or (Path(__file__).resolve().parent.parent / "config.json")
    if cfg_p.exists():
        try:
            cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
            if isinstance(cfg, dict) and cfg.get("default_output_language"):
                return str(cfg["default_output_language"]).strip().lower()
        except Exception:  # noqa: BLE001
            pass
    return "ru"


def prepare_workspace(
    evals_data: dict[str, Any],
    workspace: Path,
    applicability_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create isolated per-case run directories respecting AI applicability decisions."""
    cases = evals_data.get("evals") if isinstance(evals_data, dict) else evals_data
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evals payload must contain a non-empty 'evals' list (or top-level list).")

    app_map: dict[str, dict[str, Any]] = {}
    if applicability_data:
        for entry in applicability_data.get("cases", []):
            cid = str(entry.get("id", "")).strip()
            if cid:
                app_map[cid] = entry

    workspace.mkdir(parents=True, exist_ok=True)
    runs_dir = workspace / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    plan_cases: list[dict[str, Any]] = []
    for idx, c in enumerate(cases, start=1):
        cid = str(c.get("id", idx))
        cname = str(c.get("name", f"case-{cid}"))
        gate = app_map.get(cid, {})
        mode = str(gate.get("applicability_mode", "PENDING_AI_GATE")).upper()
        if gate and mode not in APPLICABILITY_MODES:
            raise ValueError(f"Invalid applicability_mode '{mode}' for case '{cid}'. Must be {APPLICABILITY_MODES}.")

        case_dir = runs_dir / f"case_{cid}"
        (case_dir / "with_skill").mkdir(parents=True, exist_ok=True)
        run_without = mode in {"AB_MEANINGFUL", "HYBRID"}
        if run_without:
            (case_dir / "without_skill").mkdir(parents=True, exist_ok=True)

        plan_cases.append(
            {
                "id": cid,
                "name": cname,
                "prompt": c.get("prompt", ""),
                "assertions": c.get("assertions", []),
                "applicability_mode": mode,
                "applicability_rationale": gate.get("rationale", ""),
                "with_skill_dir": str((case_dir / "with_skill").resolve()),
                "without_skill_dir": str((case_dir / "without_skill").resolve()) if run_without else None,
            }
        )

    plan = {
        "schema_version": "3.0.0",
        "skill_name": evals_data.get("skill_name", "unknown") if isinstance(evals_data, dict) else "unknown",
        "total_cases": len(plan_cases),
        "cases": plan_cases,
    }
    (workspace / "eval_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return plan


def _arm_score(arm: dict[str, Any]) -> float:
    if arm.get("output_score") is not None:
        val = float(arm["output_score"])
        if not 0.0 <= val <= 1.0:
            raise ValueError(f"output_score {val} must be in [0.0, 1.0].")
        return val
    total = float(arm.get("assertions_total", 0))
    passed = float(arm.get("assertions_passed", 0))
    if total <= 0:
        raise ValueError("Arm judgment must provide either 'output_score' or positive 'assertions_total'.")
    if passed < 0 or passed > total:
        raise ValueError(f"assertions_passed ({passed}) out of range [0, {total}].")
    return passed / total


def _runtime_score(runtime_obj: dict[str, Any] | None) -> tuple[float | None, dict[str, float | None]]:
    if not isinstance(runtime_obj, dict) or not runtime_obj:
        return None, {}
    got = 0.0
    mx = 0.0
    axis_ratios: dict[str, float | None] = {}
    for key, _, _ in RUNTIME_AXES:
        raw = runtime_obj.get(key)
        if raw is None:
            axis_ratios[key] = None
            continue
        val = float(raw)
        if not 0.0 <= val <= 5.0:
            raise ValueError(f"Runtime axis '{key}' score {val} must be in [0, 5].")
        got += val
        mx += 5.0
        axis_ratios[key] = round(val / 5.0, 4)
    return (round(got / mx, 4) if mx > 0 else None), axis_ratios


def score_benchmark(judgments: dict[str, Any], lang: str = "ru") -> dict[str, Any]:
    """Classify cases into Four Buckets / Runtime Buckets, compute honest Impact Score & Runtime Execution metrics."""
    cases = judgments.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Judgments JSON must contain a non-empty 'cases' list.")

    bucket_counts: dict[str, int] = {
        "WORKING": 0,
        "GAP": 0,
        "REDUNDANT": 0,
        "REGRESSION": 0,
        "RUNTIME_PASS": 0,
        "RUNTIME_GAP": 0,
    }
    ab_with_scores: list[float] = []
    ab_without_scores: list[float] = []
    all_runtime_ratios: list[float] = []
    axis_samples: dict[str, list[float]] = {k: [] for k, _, _ in RUNTIME_AXES}
    evaluated_cases: list[dict[str, Any]] = []

    for c in cases:
        cid = str(c.get("id", ""))
        cname = str(c.get("name", f"case-{cid}"))
        mode = str(c.get("applicability_mode", "")).upper()
        if mode not in APPLICABILITY_MODES:
            raise ValueError(f"Case '{cid}' has invalid applicability_mode '{mode}'. Expected {APPLICABILITY_MODES}.")

        ws = c.get("with_skill") or {}
        w_score = _arm_score(ws)
        rt_ratio, rt_axes = _runtime_score(ws.get("runtime_execution"))
        if rt_ratio is not None:
            all_runtime_ratios.append(rt_ratio)
            for k, v in rt_axes.items():
                if v is not None:
                    axis_samples[k].append(v)

        w_out_score: float | None = None
        delta: float | None = None
        if mode in {"AB_MEANINGFUL", "HYBRID"}:
            wo = c.get("without_skill")
            if not isinstance(wo, dict):
                raise ValueError(f"Case '{cid}' has mode '{mode}' and requires 'without_skill' judgment.")
            w_out_score = _arm_score(wo)
            delta = round(w_score - w_out_score, 4)
            ab_with_scores.append(w_score)
            ab_without_scores.append(w_out_score)

            if delta < -0.05:
                bucket = "REGRESSION"
            elif w_out_score >= 0.80 and delta <= 0.05:
                bucket = "REDUNDANT"
            elif w_score >= 0.75:
                bucket = "WORKING"
            else:
                bucket = "GAP"
        else:
            # WITH_SKILL_ONLY: A/B skipped sensibly because task is impossible without skill's unique spec/validator/script
            effective_rt = rt_ratio if rt_ratio is not None else 1.0
            if w_score >= 0.80 and effective_rt >= 0.75:
                bucket = "RUNTIME_PASS"
            else:
                bucket = "RUNTIME_GAP"

        bucket_counts[bucket] += 1
        evaluated_cases.append(
            {
                "id": cid,
                "name": cname,
                "applicability_mode": mode,
                "applicability_rationale": c.get("applicability_rationale", ""),
                "bucket": bucket,
                "with_skill_score": round(w_score, 4),
                "without_skill_score": round(w_out_score, 4) if w_out_score is not None else None,
                "ab_delta": delta,
                "runtime_execution_ratio": rt_ratio,
                "runtime_axes": rt_axes,
                "tokens_used": ws.get("tokens_used"),
                "turns_used": ws.get("turns_used"),
                "failure_notes": ws.get("failure_notes", []),
            }
        )

    ab_summary: dict[str, Any]
    if ab_with_scores:
        mean_w = sum(ab_with_scores) / len(ab_with_scores)
        mean_wo = sum(ab_without_scores) / len(ab_without_scores)
        impact_mult = round(mean_w / max(mean_wo, 0.05), 2)
        ab_summary = {
            "ab_evaluated_cases": len(ab_with_scores),
            "mean_with_skill": round(mean_w, 4),
            "mean_without_skill": round(mean_wo, 4),
            "delta_percentage_points": round((mean_w - mean_wo) * 100.0, 1),
            "impact_multiplier": impact_mult,
        }
    else:
        ab_summary = {
            "ab_evaluated_cases": 0,
            "note": "All cases classified as WITH_SKILL_ONLY (unique capability/validation impossible without skill); A/B baseline rightly skipped.",
        }

    runtime_mean = round((sum(all_runtime_ratios) / len(all_runtime_ratios)) * 100.0, 1) if all_runtime_ratios else None
    axis_averages = {
        k: (round((sum(vals) / len(vals)) * 100.0, 1) if vals else None)
        for k, vals in axis_samples.items()
    }

    has_regression = bucket_counts["REGRESSION"] > 0
    has_redundancy_only = (
        ab_summary.get("ab_evaluated_cases", 0) > 0
        and bucket_counts["REDUNDANT"] == ab_summary["ab_evaluated_cases"]
        and bucket_counts["RUNTIME_PASS"] == 0
    )
    if has_regression:
        overall_verdict = "SKILL_CAUSING_REGRESSION_REMEDIATE"
    elif has_redundancy_only:
        overall_verdict = "SKILL_REDUNDANT_FOR_FRONTIER_MODEL"
    elif bucket_counts["GAP"] > 0 or bucket_counts["RUNTIME_GAP"] > 0:
        overall_verdict = "PARTIAL_PASS_GAPS_DETECTED"
    else:
        overall_verdict = "VALIDATED_POSITIVE_IMPACT"

    return {
        "schema_version": "3.0.0",
        "output_language": lang,
        "skill_name": judgments.get("skill_name", "unknown"),
        "overall_verdict": overall_verdict,
        "total_cases": len(evaluated_cases),
        "ab_skipped_cases": sum(1 for c in evaluated_cases if c["applicability_mode"] == "WITH_SKILL_ONLY"),
        "bucket_counts": bucket_counts,
        "ab_impact_summary": ab_summary,
        "runtime_execution_summary": {
            "runtime_graded_cases": len(all_runtime_ratios),
            "mean_runtime_score_pct": runtime_mean,
            "axis_averages_pct": axis_averages,
        },
        "cases": evaluated_cases,
    }


def render_benchmark_markdown(bench: dict[str, Any]) -> str:
    is_ru = str(bench.get("output_language", "ru")).lower().startswith("ru")
    ab = bench["ab_impact_summary"]
    rt = bench["runtime_execution_summary"]
    bc = bench["bucket_counts"]

    if is_ru:
        lines = [
            f"# Отчёт AI-бенчмарка и оценки выполнения: `{bench['skill_name']}`",
            "",
            f"- **Итоговый вердикт:** `{bench['overall_verdict']}`",
            f"- **Всего кейсов:** `{bench['total_cases']}` (из них `{bench['ab_skipped_cases']}` осознанно без A/B — `WITH_SKILL_ONLY`, т.к. задача невозможна без уникальной валидации/скриптов скила)",
            f"- **Корзины (Buckets):** `WORKING`: {bc['WORKING']} · `GAP`: {bc['GAP']} · `REDUNDANT`: {bc['REDUNDANT']} · `REGRESSION`: {bc['REGRESSION']} · `RUNTIME_PASS`: {bc['RUNTIME_PASS']} · `RUNTIME_GAP`: {bc['RUNTIME_GAP']}",
        ]
        if ab.get("ab_evaluated_cases", 0) > 0:
            lines.append(
                f"- **Честный A/B Impact (по {ab['ab_evaluated_cases']} применимым кейсам):** "
                f"`{round(ab['mean_without_skill'] * 100, 1)}%` → **`{round(ab['mean_with_skill'] * 100, 1)}%`** "
                f"(`{ab['delta_percentage_points']:+}` п.п., множитель **`{ab['impact_multiplier']}x`**)"
            )
        else:
            lines.append(f"- **A/B Impact:** пропущен — {ab.get('note', '')}")

        if rt["mean_runtime_score_pct"] is not None:
            lines.append(f"- **Качество выполнения AI в рантайме (Runtime Execution Score):** **`{rt['mean_runtime_score_pct']}%`** (по {rt['runtime_graded_cases']} прогонам)")
            lines.extend(["", "## Оси оценки AI на этапе выполнения", "", "| Ось рантайма | Средний балл |", "|---|---:|"])
            for key, _, label_ru in RUNTIME_AXES:
                val = rt["axis_averages_pct"].get(key)
                lines.append(f"| {label_ru} (`{key}`) | {f'{val}%' if val is not None else 'N/A'} |")

        lines.extend(["", "## Результаты по кейсам", "", "| ID | Кейс | Режим применимости | Bucket | With Skill | Without Skill | Runtime |", "|---|---|---|---|---:|---:|---:|"])
        for c in bench["cases"]:
            ws_pct = f"{round(c['with_skill_score'] * 100)}%"
            wo_pct = f"{round(c['without_skill_score'] * 100)}%" if c["without_skill_score"] is not None else "пропущен (N/A)"
            rt_pct = f"{round(c['runtime_execution_ratio'] * 100)}%" if c["runtime_execution_ratio"] is not None else "—"
            lines.append(f"| {c['id']} | `{c['name']}` | `{c['applicability_mode']}` | **{c['bucket']}** | {ws_pct} | {wo_pct} | {rt_pct} |")
        return "\n".join(lines) + "\n"

    lines = [
        f"# Smart A/B & Runtime Execution Benchmark: `{bench['skill_name']}`",
        "",
        f"- **Overall Verdict:** `{bench['overall_verdict']}`",
        f"- **Total Cases:** `{bench['total_cases']}` (`{bench['ab_skipped_cases']}` rightly skipped A/B as `WITH_SKILL_ONLY` unique capabilities)",
        f"- **Buckets:** `WORKING`: {bc['WORKING']} · `GAP`: {bc['GAP']} · `REDUNDANT`: {bc['REDUNDANT']} · `REGRESSION`: {bc['REGRESSION']} · `RUNTIME_PASS`: {bc['RUNTIME_PASS']} · `RUNTIME_GAP`: {bc['RUNTIME_GAP']}",
    ]
    if ab.get("ab_evaluated_cases", 0) > 0:
        lines.append(
            f"- **Honest A/B Impact ({ab['ab_evaluated_cases']} meaningful cases):** "
            f"`{round(ab['mean_without_skill'] * 100, 1)}%` → **`{round(ab['mean_with_skill'] * 100, 1)}%`** "
            f"(`{ab['delta_percentage_points']:+}` pp, **`{ab['impact_multiplier']}x`**)"
        )
    if rt["mean_runtime_score_pct"] is not None:
        lines.append(f"- **Runtime Execution Score:** **`{rt['mean_runtime_score_pct']}%`**")
    lines.extend(["", "## Per-Case Breakdown", "", "| ID | Case | Mode | Bucket | With | Without | Runtime |", "|---|---|---|---|---:|---:|---:|"])
    for c in bench["cases"]:
        ws_pct = f"{round(c['with_skill_score'] * 100)}%"
        wo_pct = f"{round(c['without_skill_score'] * 100)}%" if c["without_skill_score"] is not None else "skipped (N/A)"
        rt_pct = f"{round(c['runtime_execution_ratio'] * 100)}%" if c["runtime_execution_ratio"] is not None else "—"
        lines.append(f"| {c['id']} | `{c['name']}` | `{c['applicability_mode']}` | **{c['bucket']}** | {ws_pct} | {wo_pct} | {rt_pct} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smart AI-gated A/B & Runtime Execution Benchmark helper for skill-auditor (v3.0).",
        epilog="Exit codes: 0 = success, 1 = invalid arguments/JSON, 2 = regression detected with --fail-on-regression.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="Prepare isolated run workspace & eval_plan.json from evals.json")
    p_prep.add_argument("--evals", required=True, help="Path to target skill evals/evals.json")
    p_prep.add_argument("--workspace", required=True, help="Scratch directory to initialize runs/")
    p_prep.add_argument("--applicability", help="Optional AI gate JSON classifying cases (AB_MEANINGFUL | WITH_SKILL_ONLY | HYBRID)")

    p_score = sub.add_parser("score", help="Score AI judgments into Four Buckets, honest Impact Score, and Runtime Execution metrics")
    p_score.add_argument("--judgments", required=True, help="Path to eval_judgments.json from execution-evaluator")
    p_score.add_argument("--output", "-o", default="-", help="Output benchmark JSON path (default: stdout)")
    p_score.add_argument("--markdown-out", help="Optional path to write rendered Markdown benchmark report")
    p_score.add_argument("--lang", help="Output language override (default from config.json)")
    p_score.add_argument("--fail-on-regression", action="store_true", help="Exit 2 if any REGRESSION bucket is detected")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            evals_data = load_json(Path(args.evals))
            app_data = load_json(Path(args.applicability)) if args.applicability else None
            plan = prepare_workspace(evals_data, Path(args.workspace), applicability_data=app_data)
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0

        if args.command == "score":
            judgments = load_json(Path(args.judgments))
            lang = (args.lang or load_default_language()).strip().lower()
            bench = score_benchmark(judgments, lang=lang)
            rendered = json.dumps(bench, indent=2, ensure_ascii=False)
            if args.output == "-":
                print(rendered)
            else:
                out_p = Path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(rendered + "\n", encoding="utf-8")
                print(f"Benchmark JSON written to {out_p}", file=sys.stderr)
            if args.markdown_out:
                md_p = Path(args.markdown_out)
                md_p.parent.mkdir(parents=True, exist_ok=True)
                md_p.write_text(render_benchmark_markdown(bench), encoding="utf-8")
                print(f"Benchmark Markdown written to {md_p}", file=sys.stderr)
            if args.fail_on_regression and bench["bucket_counts"]["REGRESSION"] > 0:
                return 2
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error in eval_runner: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
