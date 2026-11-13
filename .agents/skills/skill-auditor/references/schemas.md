# Schemas & Data Contracts (v3.1)

All JSON payloads exchanged between `scripts/static_audit.py`, evaluator passes/subagents (`agents/*.md`), `scripts/score_aggregator.py`, and `scripts/eval_runner.py` conform to these contracts.
Designed to enforce **hard determinism where math, coverage, SARIF, and security gates matter**, while keeping semantic judgment and runtime trace grading cleanly with the LLM.

---

## 1. `static_audit.json` (Produced by `scripts/static_audit.py`)

Supports `target_type`: `"skill-package"`, `"agents-md"`, `"cursor-mdc"`, `"agent-profile"`, `"plugin-bundle"`, or `"skill-fleet"`, plus packaged `.skill` / `.zip` archives.

```json
{
  "schema_version": "3.1.0",
  "target_path": "/abs/or/rel/path/to/target",
  "target_type": "skill-package",
  "skill_name": "my-complex-skill",
  "coverage": {
    "complete": true,
    "total_files_discovered": 14,
    "inspected_text_files": 14,
    "unreadable_or_binary_files": [],
    "symlinks": []
  },
  "tier_classification": {
    "detected_tier": "Tier 3: Complex Multi-Agent",
    "recommended_audit_path": "Full Multi-Agent (5+1) | Balanced Dual-Pass (2) | Light Single-Context (1)",
    "has_subagents": true,
    "has_child_skills": true,
    "has_mcp_references": true,
    "has_scripts": true,
    "has_references": true,
    "has_assets": false,
    "has_evals": true,
    "recommend_multi_agent_audit": true
  },
  "frontmatter": {
    "present": true,
    "valid_yaml": true,
    "yaml_error": null,
    "fields": {
      "name": "my-complex-skill",
      "description": "...",
      "license": "MIT",
      "compatibility": "...",
      "metadata": {},
      "allowed-tools": "Read Grep Glob"
    },
    "extension_fields": ["context", "agent", "hooks"],
    "checks": {
      "name_valid_format": true,
      "name_matches_dir": true,
      "name_length": 16,
      "description_present": true,
      "description_length": 412,
      "description_present": true,
      "description_first_250": "First 250 chars of description for LLM front-loading & CSO review...",
      "description_has_xml_tags": false,
      "has_frontmatter_hooks": false,
      "has_model_override": false,
      "model_override_value": null,
      "load_time_command_expansions": []
    }
  },
  "inventory": {
    "primary_file": "SKILL.md",
    "skill_md_lines": 245,
    "skill_md_bytes": 11240,
    "skill_md_words": 1420,
    "skill_md_est_tokens": 1890,
    "token_budget": {
      "skill_md_tokens": 1890,
      "references_total_tokens": 4120,
      "max_single_reference_tokens": 1850,
      "agents_total_tokens": 2200,
      "total_package_tokens": 8210,
      "pct_of_200k_window": 4.11
    },
    "total_files": 14,
    "subagent_files": ["agents/worker.md"],
    "child_skill_files": ["skills/sub-a/SKILL.md"],
    "reference_files": ["references/api.md"],
    "script_files": ["scripts/run.py"],
    "asset_files": [],
    "eval_files": ["evals/evals.json"],
    "readme_inside_skill": false,
    "config_files": []
  },
  "capability_profile": {
    "skill_name": "my-complex-skill",
    "untrusted_input": false,
    "sensitive_read": false,
    "network_egress": false
  },
  "cross_skill_chaining": {
    "detected": false,
    "lethal_trifecta": false,
    "summary": null
  },
  "ecosystem_config_checks": [],
  "child_skill_audits": [
    {
      "path": "skills/sub-a/SKILL.md",
      "skill_name": "sub-a",
      "lines": 82,
      "est_tokens": 640,
      "core_spec_pass": true,
      "smell_codes": [],
      "security_count": 0
    }
  ],
  "fleet_analysis": null,
  "link_graph": {
    "links_from_skill_md": ["references/api.md", "scripts/run.py"],
    "broken_links": [],
    "orphan_files": [],
    "nested_chain_depth_gt_1": [],
    "backslash_paths": []
  },
  "static_smells": [
    {
      "code": "BG",
      "severity": "recommendation",
      "file": "SKILL.md",
      "message": "..."
    }
  ],
  "script_checks": [
    {
      "file": "scripts/run.py",
      "language": "py",
      "lines": 90,
      "syntax_ok": true,
      "syntax_error": null,
      "imports": ["argparse", "json", "re"],
      "function_count": 3,
      "regex_call_count": 1,
      "max_string_literal_chars": 64,
      "pep723_dependencies": [],
      "typosquat_suspects": [],
      "taint_flows": [],
      "has_shebang_or_pep723": true,
      "has_help_support": true,
      "uses_interactive_input": false,
      "uses_unpinned_install": false,
      "uses_shell_true_or_eval": false,
      "supports_structured_output": true,
      "has_error_affordance_hints": true
    }
  ],
  "subagent_context_checks": [
    {
      "file": "agents/worker.md",
      "format": "markdown",
      "has_scoped_tools": true,
      "is_readonly_scoped": true,
      "has_max_turns": true,
      "has_skills_preload": false,
      "has_omit_claude_md": false,
      "est_prompt_tokens": 420,
      "notes": []
    }
  ],
  "eval_checks": [
    {
      "file": "evals/evals.json",
      "valid_json": true,
      "case_count": 3,
      "error": null
    }
  ],
  "security_findings": [
    {
      "rule_id": "SEC-PIPE-SHELL",
      "severity": "CRITICAL",
      "file": "SKILL.md",
      "line": 42,
      "snippet": "curl -sSL https://... | bash",
      "remediation": "Bundle audited script locally or pin checksum; never pipe remote content to shell."
    }
  ],
  "platform_compatibility": {
    "agentskills_core": "PASS",
    "claude_code": "PASS",
    "openai_codex": "WARN",
    "cursor": "PASS",
    "notes": ["Uses Claude-specific 'context: fork'; ensure fallback guidance for non-Claude agents."],
    "universal_portability": {
      "portability_score_pct": 89.7,
      "total_targets": 17,
      "format_ready_count": 12,
      "format_warn_count": 5,
      "format_fail_count": 0,
      "detected_install_scope": "source-package",
      "native_discovery_count": null,
      "extra_frontmatter_fields": [],
      "non_string_metadata_keys": [],
      "non_canonical_dirs": [],
      "unguarded_claude_vars": [],
      "client_path_locks": [],
      "vendor_tool_mentions": [],
      "recommendations": []
    },
    "agents": {
      "agentskills_core": { "display_name": "Agent Skills Spec (agentskills.io)", "format_status": "PASS", "auto_discovered_from_current_path": "spec-standard", "notes": [] },
      "claude_code": { "display_name": "Claude Code", "format_status": "PASS", "auto_discovered_from_current_path": "deploy-needed", "notes": [] }
    }
  }
}
```

---

## 2. Subagent / Pass Finding Output (`finding_<role>.json`)

Each specialist auditor (or inline pass) emits JSON saved by the orchestrator to `<audit_workspace>/finding_<role>.json`.

Two valid scoring modes per dimension (combine freely per dimension):
1. **Criterion-level mode** (`criterion_scores`): structured `0..5` per evaluated sub-criterion (`D1.1–D8.3`). Ideal when granular diagnostics help or on smaller models needing explicit structure.
2. **Streamlined dimension-level mode** (`dimension_score` on `0..5` scale + `issues`): skips redundant sub-boxes on simple or frontier evaluations while preserving exact weighted arithmetic and `file:line` evidence.

```json
{
  "auditor_id": "trigger-context-auditor",
  "evaluated_dimensions": ["D1", "D2"],
  "dimension_assessments": [
    {
      "dimension_id": "D1",
      "applicable": true,
      "na_reason": null,
      "criterion_scores": [
        {
          "criterion_id": "D1.1",
          "name": "Spec & Naming Validity",
          "score": 5,
          "max_score": 5,
          "evidence": "SKILL.md frontmatter has name='foo' matching directory; description is 384 chars without XML tags.",
          "issues": []
        },
        {
          "criterion_id": "D1.2",
          "name": "Trigger Triad & Front-Loading",
          "score": 3,
          "max_score": 5,
          "evidence": "First 250 chars explain implementation details instead of user intent; lacks negative boundaries.",
          "issues": [
            {
              "id": "D1-01",
              "priority": "P1",
              "smell_code": "CSD",
              "location": "SKILL.md:3",
              "title": "Weak front-loaded trigger intent",
              "impact": "Under-triggers when Codex truncates catalog or Claude matches on short descriptions.",
              "fix_suggestion": "Rewrite description starting with action + user triggers + 'Do NOT use when...'"
            }
          ]
        }
      ],
      "dimension_summary": "Concise verdict on D1."
    },
    {
      "dimension_id": "D2",
      "applicable": true,
      "na_reason": null,
      "dimension_score": 4.5,
      "dimension_max": 5.0,
      "evidence": "Lean 65-line frontier-friendly SKILL.md with 1-level links and zero duplication.",
      "issues": [],
      "dimension_summary": "Concise verdict on D2."
    }
  ],
  "security_veto_flags": [],
  "cleared_static_findings": [
    {
      "rule_id": "SEC-PIPE-SHELL",
      "location": "references/anti-patterns.md:14",
      "reason": "Passive warning table instructing the agent never to pipe remote URLs to shell; not an executable directive."
    }
  ],
  "beyond_rubric_insights": [
    "Optional architectural insight not captured by the 8 rubric dimensions (e.g. target model fit, radical simplification idea)."
  ],
  "script_rationality_reviews": [
    {
      "file": "scripts/run.py",
      "verdict": "JUSTIFIED | SCRIPT_OVERREACH | REDUNDANT",
      "purpose": "Schema/AST validation across 100+ files.",
      "rationale": "Deterministic checks where LLM improvisation degrades.",
      "recommended_split": null
    }
  ],
  "cross_agent_conflicts_or_notes": []
}
```

### Criterion / Dimension Score Scale (`0–5`)
- `5`: Exemplary — meets core invariants and best-practice intent for its target model tier, zero meaningful defects.
- `4`: Strong — solid design, only minor polish recommendations.
- `3`: Adequate — functional on happy paths, clear opportunities to improve reliability or clarity.
- `2`: Weak — major omissions, ambiguity, context bloat, or fragile assumptions.
- `1`: Deficient — actively misleads agent or breaks execution.
- `0`: Missing / Critical Failure — absent when essential or causes severe failure.

---

## 3. Hard Security Gate Values (`security_veto_flags` & `cleared_static_findings`)

- `CRITICAL` (`cap_score_at: 39`, Grade `F`, verdict `BLOCKED_REMEDIATE_CRITICAL_ISSUES`)
- `HIGH` (`cap_score_at: 69`, Grade `C`, verdict `NEEDS_REFACTORING_BEFORE_USE`)

Static `CRITICAL`/`HIGH` hits from `static_audit.json["security_findings"]` automatically trigger gates **UNLESS** explicitly waived in `cleared_static_findings` with exact `(rule_id, location, reason)` by `security-safety-auditor` (or the inline security pass). This prevents false `F` scores on legitimate DevSecOps / security skills without weakening real security gates.

---

## 4. Final Aggregated Report (`audit_summary.json` from `scripts/score_aggregator.py`)

```json
{
  "schema_version": "3.0.0",
  "output_language": "ru",
  "policy_profile": "balanced",
  "skill_name": "my-complex-skill",
  "target_type": "skill-package",
  "skill_tier": "Tier 3: Complex Multi-Agent",
  "final_score": 84.0,
  "uncapped_score": 84.0,
  "grade": "B",
  "verdict": "PASS_WITH_RECOMMENDATIONS",
  "security_gate": "CLEAR",
  "coverage_status": "COMPLETE",
  "unreadable_or_binary_files": [],
  "token_budget": {},
  "security_veto_flags": [],
  "cleared_static_findings": [],
  "platform_compatibility": {},
  "dimension_breakdown": [
    {
      "dimension_id": "D1",
      "name": "Triggering & Discoverability",
      "weight_base": 14.0,
      "weight_effective": 14.0,
      "applicable": true,
      "raw_ratio": 0.85,
      "weighted_points": 11.9,
      "rating": "Strong"
    }
  ],
  "script_rationality_reviews": [],
  "top_smells_detected": ["RL", "BG"],
  "prioritized_actions": {
    "P0_blockers": [],
    "P1_high_impact": [],
    "P2_polish": []
  },
  "roi_top_actions": [
    {
      "id": "D1-01",
      "priority": "P1",
      "dimension_id": "D1",
      "location": "SKILL.md:3",
      "title": "Weak front-loaded trigger intent",
      "estimated_score_gain": 2.1,
      "gate_unlock_potential": 0.0
    }
  ],
  "beyond_rubric_insights": [],
  "cross_agent_notes": []
}
```

### Canonical Enums
- **Ratings**: `Exemplary` (`>=90%`), `Strong` (`>=75%`), `Adequate` (`>=60%`), `Weak` (`>=40%`), `Critical` (`<40%`), `N/A`.
- **Verdicts**: `PRODUCTION_READY` (A), `PASS_WITH_RECOMMENDATIONS` (B), `CONDITIONAL_PASS_IMPROVE_RELIABILITY` (C), `MANUAL_REVIEW_REQUIRED_INCOMPLETE_COVERAGE` (when `coverage_status == "INCOMPLETE_COVERAGE"`), `NEEDS_REFACTORING_BEFORE_USE` (D / High Gate / Spec Fail), `BLOCKED_REMEDIATE_CRITICAL_ISSUES` (F / Critical Gate).
- **Security Gates**: `CLEAR`, `INCOMPLETE_COVERAGE`, `CAPPED_HIGH`, `BLOCKED_CRITICAL`.

---

## 5. Smart A/B & Runtime Execution Eval Contracts (`scripts/eval_runner.py`)

### 5.1 AI Gate (`eval_applicability.json`)
```json
{
  "skill_name": "my-skill",
  "cases": [
    {
      "id": "1",
      "applicability_mode": "WITH_SKILL_ONLY",
      "rationale": "Task validates a strict proprietary document schema + bundled script impossible without the skill; without_skill baseline omitted."
    },
    {
      "id": "2",
      "applicability_mode": "AB_MEANINGFUL",
      "rationale": "Frontier LLM can attempt SQL optimization without the skill; run A/B to measure Impact Score and Regression/Redundancy."
    }
  ]
}
```

### 5.2 AI Execution Judgments (`eval_judgments.json` -> `eval_benchmark.json`)
```json
{
  "skill_name": "my-skill",
  "cases": [
    {
      "id": "1",
      "name": "strict-schema-validation",
      "applicability_mode": "WITH_SKILL_ONLY",
      "applicability_rationale": "Unique schema validator impossible without skill.",
      "with_skill": {
        "assertions_passed": 4,
        "assertions_total": 4,
        "runtime_execution": {
          "progressive_disclosure": 5,
          "script_and_tool_discipline": 5,
          "invariant_and_guardrail_compliance": 5,
          "context_and_turn_economy": 4,
          "output_spec_accuracy": 5
        },
        "tokens_used": 6200,
        "turns_used": 4,
        "failure_notes": []
      }
    }
  ]
}
```
