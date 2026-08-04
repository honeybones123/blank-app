"""Audit target-band candidate winner policy boundary."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def build_payload() -> dict:
    source = _read(AUTO_DESIGN_COMPUTE)
    start, end, segment = _function_segment(source, "_solve_one_click_to_target")
    checks = {
        "sort_key_service_delegated": "_resolve_target_band_candidate_sort_key(" in segment,
        "winner_selection_service_delegated": "_select_target_band_ranked_candidate(scored)" in segment,
        "page_lexicographic_sort_removed": 'scored.sort(key=lambda x: x["sort_key"])' not in segment,
        "page_best_candidate_assignment_removed": "best = scored[0]" not in segment,
        "step_improvement_policy_delegated": "_one_click_step_improves(" in segment,
        "in_band_shear_override_still_page_owned": "_one_click_in_band_shear_cleanup_candidate_allowed(" in segment,
        "post_selection_evaluation_still_page_owned": "evaluate_candidate_full(" in segment and "one_click_after_step_" in segment,
        "working_state_commit_still_page_owned": "working.update(best[\"updates\"])" in segment,
        "fallback_next_hop_still_page_owned": "_one_click_best_next_hop_improving_candidate(" in segment,
        "selected_candidate_acceptance_service_delegated": "_resolve_target_band_selected_candidate_acceptance(" in segment,
        "stop_trace_string_retained": "no_improving_candidate" in segment,
    }
    classifications = [
        {
            "surface": "lexicographic winner selection from scored candidates",
            "current_owner": "design_brain.candidate_evaluation",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "SERVICE_OWNED",
            "reason": "selection depends only on plain scored candidate dictionaries and their sort_key values",
        },
        {
            "surface": "no-improvement stop decision",
            "current_owner": "design_brain.candidate_evaluation for pure accept/reject; solver keeps trace shaping",
            "target_owner": "candidate_evaluation/controller after parity",
            "classification": "SERVICE_OWNED_WITH_TRACE_SHAPING_RETAINED",
            "reason": "step-improves and accept/reject policy are service-owned; solver still computes the shear override and emits the legacy stop trace",
        },
        {
            "surface": "in-band shear cleanup deferral override",
            "current_owner": "inputs_page.py",
            "target_owner": "candidate_evaluation/controller later",
            "classification": "NOT_READY",
            "reason": "still calls page-local shear cleanup allowance policy and interacts with route-specific deferral state",
        },
        {
            "surface": "post-selection evaluate/apply-to-working-state loop",
            "current_owner": "inputs_page.py",
            "target_owner": "candidate_evaluation service later",
            "classification": "NOT_READY",
            "reason": "mutates working state, canonicalizes state, performs full evaluation, and emits detailed traces",
        },
        {
            "surface": "fallback next-hop injection",
            "current_owner": "inputs_page.py",
            "target_owner": "controller/candidate_evaluation after separate adapter proof",
            "classification": "NOT_READY",
            "reason": "adds a synthetic fallback candidate and depends on exhaustion/refinement route policy",
        },
    ]
    blockers = [
        "post-selection evaluation still calls page-local/full evaluator flow",
        "fallback next-hop injection is still page-owned route policy",
        "in-band shear cleanup override is still route-state dependent",
    ]
    first_safe_slice = "audit/extract fallback next-hop injection or post-selection evaluation boundary separately"
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "target_band_candidate_winner_policy",
        "function": "_solve_one_click_to_target",
        "line_range": [start, end],
        "checks": checks,
        "classifications": classifications,
        "ready_to_extract_now": [] if status == "PASS" else [],
        "not_ready": [
            "in-band shear cleanup deferral override",
            "post-selection evaluate/apply-to-working-state loop",
            "fallback next-hop injection",
        ],
        "blockers": blockers,
        "first_safe_implementation_slice": first_safe_slice,
        "required_verifier": "dedicated fallback next-hop or post-selection evaluation boundary audit",
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_candidate_winner_policy_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_candidate_winner_policy_boundary_audit_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Candidate Winner Policy Boundary Audit",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        "The target-band sort-key construction, lexicographic winner pick, and pure accept/reject decision are now service-owned. Remaining route logic is fallback injection, override calculation, trace shaping, and post-selection evaluation.",
        "",
        "## Checks",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Classification"])
    for row in payload["classifications"]:
        lines.append(f"- `{row['surface']}`: `{row['classification']}` -> {row['target_owner']}. {row['reason']}")
    lines.extend(
        [
            "",
            "## First Safe Implementation Slice",
            "",
            str(payload["first_safe_implementation_slice"]),
            "",
            "## Stop Conditions",
            "",
            "- Do not move no-improvement stop shaping yet.",
            "- Do not move in-band shear cleanup deferral override yet.",
            "- Do not move post-selection evaluation or working-state mutation yet.",
            "- Do not move fallback next-hop injection yet.",
            "",
            f"JSON artifact: `{json_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
