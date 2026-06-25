from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
RUNTIME_PATH = ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py"

from design_brain.families.shear_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    internal_strategy_lanes,
    load_shear_fail_governs_contract,
    ranking_criteria,
)
from design_brain.families.shear_fail_governs.runtime import (  # noqa: E402
    ShearFailGovernsResult,
    run_shear_fail_governs_ladder_runtime,
    shear_fail_governs_contract_lane_order,
)
from design_brain.shear_candidate_evaluation import (  # noqa: E402
    ShearCandidateEvaluation,
    ShearCandidateInput,
    ShearCandidateUpdate,
    build_shear_candidate_state_hash,
)


EXPECTED_LANE_ORDER = (
    "SPACING_REDUCTION",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
    "NO_VALID_REPAIR",
)
EXPECTED_RANKING = (
    "target band achieved",
    "smallest geometry change",
    "smallest reinforcement increase",
    "constructability",
    "cost proxy",
)
REQUIRED_RESULT_FIELDS = {
    "selected_strategy_lane",
    "ladder_trace",
    "candidate_repairs",
    "selected_recommendation",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "ranking_proof",
    "exact_stop_proof",
    "exhausted_reason",
    "no_valid_repair_proof",
    "repair_reason_proof",
    "blocked_reason",
    "cta_intent_proof",
    "ladder_hash",
}
FORBIDDEN_IMPORT_ROOTS = {"inputs_page", "streamlit"}
FORBIDDEN_IMPORT_PREFIXES = {
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
    "design_brain.families.bending",
    "design_brain.families.bending_fail",
    "design_brain.families.bending_fail_governs",
}
FORBIDDEN_SOURCE_TERMS = {
    "session_state",
    "st.",
    "button_contract",
    "final_button_label",
    "publication",
    "apply_routing",
    "one_click",
    "rendered_html",
    "visible wording",
}


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_imports(path: Path) -> list[str]:
    blocked: list[str] = []
    for imported in _module_imports(path):
        root = imported.split(".", 1)[0]
        if root in FORBIDDEN_IMPORT_ROOTS:
            blocked.append(imported)
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES):
            blocked.append(imported)
    return sorted(set(blocked))


def _forbidden_source_hits(path: Path) -> list[str]:
    lowered = path.read_text(encoding="utf-8").lower()
    return sorted(term for term in FORBIDDEN_SOURCE_TERMS if term.lower() in lowered)


def _base_state(*, current_util: float = 1.2, constraints_prohibit: bool = False) -> dict[str, Any]:
    return {
        "geometry": {
            "beam_width_mm": 400.0,
            "beam_depth_mm": 600.0,
            "effective_depth_mm": 540.0,
        },
        "reinforcement": {
            "ligature_spacing_mm": 300.0,
            "ligature_diameter_mm": 10,
            "ligature_leg_count": 2,
        },
        "actions": {
            "current_shear_utilisation": current_util,
            "design_shear_kn": 440.0,
        },
        "constraints": {
            "minimum_spacing_mm": 100.0,
            "constraints_prohibit_remaining_repairs": constraints_prohibit,
        },
    }


def _evaluation(
    boundary_input: ShearCandidateInput,
    update: ShearCandidateUpdate,
    *,
    shear_utilisation: float,
    status: str,
) -> ShearCandidateEvaluation:
    return ShearCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=update.update_hash,
        candidate_state_hash=build_shear_candidate_state_hash(boundary_input.base_state, update.updates),
        shear_utilisation=shear_utilisation,
        previous_shear_utilisation=1.2,
        utilisation_improved=shear_utilisation < 1.2,
        code_compliance_status={"overall": status},
        constructability_status={"overall": status},
        spacing_status={"status": status},
        bar_size_status={"status": status},
        leg_count_status={"status": status},
        geometry_status={"status": status},
        capacity_summary={"normalised": True},
        failure_flags={"shear_fail": shear_utilisation > 1.0},
        engineering_status={"overall": status, "target_band_status": "TARGET" if 0.85 <= shear_utilisation <= 1.0 else "FAIL"},
    ).with_evaluation_hash()


def _rejecting_evaluator(boundary_input: ShearCandidateInput, update: ShearCandidateUpdate) -> ShearCandidateEvaluation:
    return _evaluation(boundary_input, update, shear_utilisation=1.2, status="FAIL")


def _spacing_accepting_evaluator(boundary_input: ShearCandidateInput, update: ShearCandidateUpdate) -> ShearCandidateEvaluation:
    reinforcement = dict((update.updates or {}).get("reinforcement") or {})
    if reinforcement.get("ligature_spacing_mm") == 100:
        return _evaluation(boundary_input, update, shear_utilisation=0.93, status="PASS")
    return _evaluation(boundary_input, update, shear_utilisation=1.2, status="FAIL")


def _stable_json_hash(value: Any) -> str:
    from design_brain.shear_candidate_evaluation import stable_shear_candidate_hash

    return stable_shear_candidate_hash(value)


def _trace_by_lane(result: ShearFailGovernsResult) -> dict[str, dict[str, Any]]:
    return {str(row.get("lane_id") or ""): dict(row) for row in result.ladder_trace}


def _restart_lanes_for(trace: dict[str, dict[str, Any]], lane_id: str) -> set[tuple[str, ...]]:
    row = trace.get(lane_id) or {}
    return {
        tuple(item.get("restart_lanes") or ())
        for item in row.get("restart_evidence") or ()
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_FAIL_GOVERNS Ladder Runtime Snapshot",
        "",
        f"Status: {snapshot.get('status')}",
        "",
        "## Scope",
        "",
        "- Runtime/proof only.",
        "- No product cutover.",
        "- No CTA rendering, publication, apply routing, one-click orchestration, visible wording, UI/session/debug ownership moved.",
        "- No BENDING files touched.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (snapshot.get("checks") or {}).items())
    lines.extend(["", "## Runtime Hashes", ""])
    lines.extend(
        [
            f"- no_valid_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('no_valid_ladder_hash')}`",
            f"- exact_stop_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('exact_stop_ladder_hash')}`",
            f"- selected_repair_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('selected_repair_ladder_hash')}`",
        ]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    contract = load_shear_fail_governs_contract()
    contract_lane_order = tuple(str(lane.get("lane_id") or "") for lane in internal_strategy_lanes())
    runtime_lane_order = shear_fail_governs_contract_lane_order()

    no_valid_result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(current_util=1.2, constraints_prohibit=True),
        evaluate_candidate=_rejecting_evaluator,
    )
    repeated_no_valid_result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(current_util=1.2, constraints_prohibit=True),
        evaluate_candidate=_rejecting_evaluator,
    )
    exact_stop_result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(current_util=0.92, constraints_prohibit=False),
        evaluate_candidate=_rejecting_evaluator,
    )
    selected_repair_result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(current_util=1.2, constraints_prohibit=False),
        evaluate_candidate=_spacing_accepting_evaluator,
    )

    no_valid_trace = _trace_by_lane(no_valid_result)
    selected_repair_trace = _trace_by_lane(selected_repair_result)
    result_fields = {field.name for field in fields(ShearFailGovernsResult)}
    cta_proof = dict(selected_repair_result.cta_intent_proof or {})

    checks = {
        "contract_loads": bool(contract),
        "contract_family_id": (contract.get("family_identity") or {}).get("family_id") == "SHEAR_FAIL_GOVERNS",
        "runtime_lane_order_equals_contract": runtime_lane_order == contract_lane_order == EXPECTED_LANE_ORDER,
        "spacing_policy_represented": (no_valid_trace.get("SPACING_REDUCTION") or {}).get("candidate_count") == 7,
        "bar_policy_represented": (no_valid_trace.get("BAR_SIZE_INCREASE") or {}).get("candidate_count") == 21,
        "depth_policy_represented": (no_valid_trace.get("DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get("candidate_count") == 21,
        "width_policy_represented": (no_valid_trace.get("WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get("candidate_count") == 21,
        "leg_policy_represented": (no_valid_trace.get("LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get("candidate_count") == 63,
        "bar_restart_recorded": _restart_lanes_for(no_valid_trace, "BAR_SIZE_INCREASE") == {("SPACING_REDUCTION",)},
        "depth_restart_recorded": _restart_lanes_for(no_valid_trace, "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") == {("SPACING_REDUCTION", "BAR_SIZE_INCREASE")},
        "width_restart_recorded": _restart_lanes_for(no_valid_trace, "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") == {("SPACING_REDUCTION", "BAR_SIZE_INCREASE")},
        "leg_restart_recorded": _restart_lanes_for(no_valid_trace, "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH") == {("SPACING_REDUCTION", "BAR_SIZE_INCREASE")},
        "ranking_follows_contract_order": tuple(ranking_criteria()) == EXPECTED_RANKING and tuple(selected_repair_result.ranking_proof.get("criteria") or ()) == EXPECTED_RANKING,
        "exact_stop_only_inside_target_band": exact_stop_result.selected_strategy_lane == "EXACT_STOP" and exact_stop_result.exact_stop_proof.get("allowed") is True and no_valid_result.exact_stop_proof.get("allowed") is False,
        "exhausted_has_proof": bool(no_valid_result.exhausted_reason),
        "no_valid_has_proof": bool(no_valid_result.no_valid_repair_proof.get("allowed")) and no_valid_result.selected_strategy_lane == "NO_VALID_REPAIR",
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "ladder_hash_stable": no_valid_result.ladder_hash == repeated_no_valid_result.ladder_hash,
        "candidate_evaluation_boundary_used": bool((no_valid_result.candidate_repairs or ({},))[0].get("evaluation_hash")),
        "cta_intent_proof_only_not_rendered_or_applied": cta_proof.get("proof_only") is True and cta_proof.get("product_driving") is False and cta_proof.get("rendered") is False and cta_proof.get("applied") is False,
        "runtime_has_no_page_shared_ui_imports": not _forbidden_imports(RUNTIME_PATH) and not _forbidden_source_hits(RUNTIME_PATH),
        "no_bending_imports": not any("bending" in imported for imported in _module_imports(RUNTIME_PATH)),
    }
    failures = [key for key, passed in checks.items() if not passed]

    snapshot = {
        "schema": "shear_fail_governs_ladder_runtime_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_lane_order": contract_lane_order,
        "runtime_lane_order": runtime_lane_order,
        "checks": checks,
        "forbidden_imports": _forbidden_imports(RUNTIME_PATH),
        "forbidden_source_hits": _forbidden_source_hits(RUNTIME_PATH),
        "scenario_hashes": {
            "no_valid_ladder_hash": no_valid_result.ladder_hash,
            "repeat_no_valid_ladder_hash": repeated_no_valid_result.ladder_hash,
            "exact_stop_ladder_hash": exact_stop_result.ladder_hash,
            "selected_repair_ladder_hash": selected_repair_result.ladder_hash,
        },
        "scenario_summaries": {
            "no_valid": {
                "selected_strategy_lane": no_valid_result.selected_strategy_lane,
                "candidate_count": len(no_valid_result.candidate_repairs),
                "exhausted_reason": no_valid_result.exhausted_reason,
                "no_valid_repair_proof": no_valid_result.no_valid_repair_proof,
            },
            "exact_stop": {
                "selected_strategy_lane": exact_stop_result.selected_strategy_lane,
                "exact_stop_proof": exact_stop_result.exact_stop_proof,
            },
            "selected_repair": {
                "selected_strategy_lane": selected_repair_result.selected_strategy_lane,
                "selected_recommendation": selected_repair_result.selected_recommendation,
                "ranking_proof": selected_repair_result.ranking_proof,
                "cta_intent_proof": selected_repair_result.cta_intent_proof,
                "spacing_lane_trace": selected_repair_trace.get("SPACING_REDUCTION"),
            },
        },
        "snapshot_hash": _stable_json_hash(
            {
                "contract_lane_order": contract_lane_order,
                "runtime_lane_order": runtime_lane_order,
                "scenario_hashes": {
                    "no_valid_ladder_hash": no_valid_result.ladder_hash,
                    "exact_stop_ladder_hash": exact_stop_result.ladder_hash,
                    "selected_repair_ladder_hash": selected_repair_result.ladder_hash,
                },
                "checks": checks,
            }
        ),
        "failures": failures,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_governs_ladder_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_ladder_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)

    print(f"{snapshot['status']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
