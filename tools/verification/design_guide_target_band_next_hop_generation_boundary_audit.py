"""Audit target-band next-hop candidate generation/evaluation boundary."""

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
    start, end, helper = _function_segment(source, "_one_click_best_next_hop_improving_candidate")
    solve_start, solve_end, solve = _function_segment(source, "_solve_one_click_to_target")
    checks = {
        "helper_present": "def _one_click_best_next_hop_improving_candidate(" in source,
        "called_from_target_solver": "_one_click_best_next_hop_improving_candidate(cur_eval, mode_config)" in solve,
        "uses_page_auto_design_context": "_build_auto_design_context(" in helper,
        "uses_refinement_candidate_generator": "generate_compliant_refinement_candidates(" in helper,
        "uses_full_candidate_evaluator": "evaluate_candidate_full(" in helper,
        "uses_canonical_state_pack": "_build_canonical_design_state_pack(" in helper,
        "uses_update_diff": "_one_click_diff_accumulated_updates(" in helper,
        "uses_spacing_envelope_guard": "_one_click_has_unresolved_spacing_envelope_fail(" in helper,
        "uses_service_owned_step_improves_wrapper": "_one_click_step_improves(" in helper,
        "returns_plain_payload": '"state": dict(candidate_state)' in helper and '"updates": dict(candidate_updates)' in helper,
    }
    classifications = [
        {
            "surface": "precheck guards before generating next-hop candidates",
            "classification": "READY_FOR_SMALL_POLICY_EXTRACTION",
            "current_owner": "inputs_page.py",
            "target_owner": "design_brain.candidate_evaluation",
            "reason": "non-dict, all_key_pass, strict-band, finite-distance, and state-present checks are pure scalar/eval checks",
        },
        {
            "surface": "auto-design context construction",
            "classification": "NOT_READY",
            "current_owner": "inputs_page.py",
            "target_owner": "candidate generation service later",
            "reason": "uses page-local context builder and current state normalisation",
        },
        {
            "surface": "compliant refinement candidate generation",
            "classification": "NOT_READY",
            "current_owner": "inputs_page.py/service mix",
            "target_owner": "candidate generation service later",
            "reason": "generator call is coupled to auto-design context and candidate-state iteration",
        },
        {
            "surface": "full candidate evaluation loop",
            "classification": "NOT_READY",
            "current_owner": "inputs_page.py",
            "target_owner": "candidate_evaluation service later",
            "reason": "calls full evaluator and canonical state pack directly",
        },
        {
            "surface": "candidate target-domain attachment and update diff",
            "classification": "NOT_READY",
            "current_owner": "inputs_page.py",
            "target_owner": "candidate_evaluation service later",
            "reason": "mutates candidate eval target-domain metadata and uses page diff helper",
        },
        {
            "surface": "best payload selection by distance",
            "classification": "READY_AFTER_PRECHECK_EXTRACTION",
            "current_owner": "inputs_page.py",
            "target_owner": "design_brain.candidate_evaluation",
            "reason": "selection over evaluated candidate payload rows is plain-data once rows exist",
        },
    ]
    first_safe_slice = (
        "extract next-hop precheck policy only; do not move generator/evaluator loop until "
        "candidate generation and full-evaluation service inputs are proven"
    )
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "surface": "target_band_next_hop_generation_boundary",
        "helper_segment": {"function": "_one_click_best_next_hop_improving_candidate", "start_line": start, "end_line": end},
        "solve_segment": {"function": "_solve_one_click_to_target", "start_line": solve_start, "end_line": solve_end},
        "checks": checks,
        "classifications": classifications,
        "ready_to_extract_now": ["precheck guards before generating next-hop candidates"] if status == "PASS" else [],
        "not_ready": [
            "auto-design context construction",
            "compliant refinement candidate generation",
            "full candidate evaluation loop",
            "candidate target-domain attachment and update diff",
        ],
        "first_safe_implementation_slice": first_safe_slice,
        "required_verifier": "design_guide_target_band_next_hop_precheck_policy_extraction.py",
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_next_hop_generation_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_next_hop_generation_boundary_audit_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Next-Hop Generation Boundary Audit",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        "The full next-hop generator/evaluator loop is not ready to move. The only safe next extraction is the pure precheck gate before generation starts.",
        "",
        "## Checks",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Classification"])
    for row in payload["classifications"]:
        lines.append(f"- `{row['surface']}`: `{row['classification']}` -> {row['target_owner']}. {row['reason']}")
    lines.extend(["", "## First Safe Implementation Slice", "", str(payload["first_safe_implementation_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
