"""Audit target-band candidate winner policy boundary."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
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
    source = _read(INPUTS)
    start, end, segment = _function_segment(source, "_solve_one_click_to_target")
    checks = {
        "sort_key_service_delegated": "_resolve_target_band_candidate_sort_key(" in segment,
        "page_lexicographic_sort_still_present": 'scored.sort(key=lambda x: x["sort_key"])' in segment,
        "page_best_candidate_assignment_still_present": "best = scored[0]" in segment,
        "step_improvement_policy_delegated": "_one_click_step_improves(" in segment,
        "in_band_shear_override_still_page_owned": "_one_click_in_band_shear_cleanup_candidate_allowed(" in segment,
        "post_selection_evaluation_still_page_owned": "evaluate_candidate_full(" in segment and "one_click_after_step_" in segment,
        "working_state_commit_still_page_owned": "working.update(best[\"updates\"])" in segment,
        "fallback_next_hop_still_page_owned": "_one_click_best_next_hop_improving_candidate(" in segment,
        "stop_reason_assignment_still_page_owned": "stop_reason = \"no_improving_candidate\"" in segment,
    }
    classifications = [
        {
            "surface": "lexicographic winner selection from scored candidates",
            "current_owner": "inputs_page.py",
            "target_owner": "design_brain.candidate_evaluation",
            "classification": "READY_FOR_SELECTION_ONLY_EXTRACTION",
            "reason": "selection depends only on plain scored candidate dictionaries and their sort_key values",
        },
        {
            "surface": "no-improvement stop decision",
            "current_owner": "inputs_page.py wrapper calling service policy",
            "target_owner": "candidate_evaluation/controller after parity",
            "classification": "PARTIAL_SERVICE_OWNED",
            "reason": "step-improves policy is service-owned, but page still combines it with shear cleanup deferral override and trace/stop shaping",
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
    first_safe_slice = "extract selection-only helper that returns the lexicographic minimum scored candidate without moving improvement/override/evaluation logic"
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "target_band_candidate_winner_policy",
        "function": "_solve_one_click_to_target",
        "line_range": [start, end],
        "checks": checks,
        "classifications": classifications,
        "ready_to_extract_now": ["lexicographic winner selection from scored candidates"] if status == "PASS" else [],
        "not_ready": [
            "no-improvement stop decision as a whole",
            "in-band shear cleanup deferral override",
            "post-selection evaluate/apply-to-working-state loop",
            "fallback next-hop injection",
        ],
        "blockers": blockers,
        "first_safe_implementation_slice": first_safe_slice,
        "required_verifier": "design_guide_target_band_candidate_winner_selection_service_extraction.py",
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
        "The target-band sort-key construction is now service-owned. The next safe extraction is only the lexicographic selected-candidate pick.",
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
