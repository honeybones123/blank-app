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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "serviceability_governs" / "runtime.py"

from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    load_serviceability_governs_contract,
    ranking_criteria,
    serviceability_contract_lane_order,
)
from design_brain.families.serviceability_governs.runtime import (  # noqa: E402
    ServiceabilityGovernsResult,
    ServiceabilityInputs,
    run_serviceability_governs_ladder_runtime,
)
from design_brain.serviceability_candidate_evaluation import (  # noqa: E402
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    build_serviceability_candidate_state_hash,
    stable_serviceability_candidate_hash,
)


EXPECTED_LANE_ORDER = (
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
)
EXPECTED_RANKING = (
    "serviceability compliance achieved",
    "smallest geometry increase",
    "smallest reinforcement increase",
    "constructability",
    "cost proxy",
)
REQUIRED_RESULT_FIELDS = {
    "status",
    "selected_strategy_lane",
    "selected_recommendation",
    "candidate_repairs",
    "exhausted_reason",
    "evidence",
    "ladder_trace",
    "accepted_lane_evidence",
    "rejected_lane_evidence",
    "ranking_evidence",
    "exact_stop_proof",
    "exhausted_proof",
    "ownership_proof",
    "ladder_hash",
}
FORBIDDEN_IMPORT_ROOTS = {"inputs_page", "streamlit"}
FORBIDDEN_IMPORT_PREFIXES = {
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
}
FORBIDDEN_SOURCE_TERMS = {
    "session_state",
    "st.",
    "button_contract",
    "final_button_label",
    "publication",
    "cta_",
    "cta intent",
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


def _base_state(*, current_utilisation: float = 1.2, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "geometry": {
            "beam_width_mm": 300.0,
            "beam_depth_mm": 500.0,
            "span_mm": 6500.0,
        },
        "reinforcement": {
            "bottom_bar_count": 3,
            "bottom_bar_diameter_mm": 20,
        },
        "actions": {
            "current_serviceability_utilisation": current_utilisation,
        },
        "failure_flags": {
            "bending_fail": False,
            "shear_fail": False,
        },
        "constraints": {
            "maximum_depth_mm": 650.0,
            "maximum_width_mm": 450.0,
            "blocker_reasons": blockers or [],
        },
    }


def _evaluation(
    boundary_input: ServiceabilityCandidateInput,
    update: ServiceabilityCandidateUpdate,
    *,
    serviceability_utilisation: float,
    serviceability_compliant: bool,
    bending_fail: bool = False,
    shear_fail: bool = False,
    blocker_reasons: list[str] | None = None,
) -> ServiceabilityCandidateEvaluation:
    return ServiceabilityCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=update.update_hash,
        candidate_state_hash=build_serviceability_candidate_state_hash(boundary_input.base_state, update.updates),
        serviceability_utilisation=serviceability_utilisation,
        previous_serviceability_utilisation=1.2,
        serviceability_improved=serviceability_utilisation < 1.2,
        serviceability_compliant=serviceability_compliant,
        deflection_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        crack_control_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        strength_status={
            "overall": "FAIL" if bending_fail or shear_fail else "PASS",
            "bending": "FAIL" if bending_fail else "PASS",
            "shear": "FAIL" if shear_fail else "PASS",
        },
        code_compliance_status={"overall": "PASS"},
        constructability_status={"overall": "PASS"},
        geometry_status={"status": "CHECKED"},
        reinforcement_status={"status": "CHECKED"},
        blocker_status={
            "blocked": bool(blocker_reasons),
            "reasons": blocker_reasons or [],
        },
        capacity_summary={"normalised": True},
        failure_flags={
            "serviceability_fail": not serviceability_compliant,
            "bending_fail": bending_fail,
            "shear_fail": shear_fail,
            "constructability_fail": False,
        },
        engineering_status={"overall": "PASS" if serviceability_compliant and not bending_fail and not shear_fail else "FAIL"},
    ).with_evaluation_hash()


def _rejecting_evaluator(
    boundary_input: ServiceabilityCandidateInput,
    update: ServiceabilityCandidateUpdate,
) -> ServiceabilityCandidateEvaluation:
    return _evaluation(
        boundary_input,
        update,
        serviceability_utilisation=1.08,
        serviceability_compliant=False,
        blocker_reasons=["geometry limits reached"],
    )


def _bottom_accepting_evaluator(
    boundary_input: ServiceabilityCandidateInput,
    update: ServiceabilityCandidateUpdate,
) -> ServiceabilityCandidateEvaluation:
    reinforcement = dict((update.updates or {}).get("reinforcement") or {})
    if reinforcement.get("bottom_bar_count") == 4:
        return _evaluation(boundary_input, update, serviceability_utilisation=0.96, serviceability_compliant=True)
    return _evaluation(boundary_input, update, serviceability_utilisation=1.11, serviceability_compliant=False)


def _trace_by_lane(result: ServiceabilityGovernsResult) -> dict[str, dict[str, Any]]:
    return {str(row.get("lane_id") or ""): dict(row) for row in result.ladder_trace}


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SERVICEABILITY_GOVERNS Ladder Runtime Snapshot",
        "",
        f"Status: `{snapshot.get('status')}`",
        "",
        "## Scope",
        "",
        "- Runtime/proof only.",
        "- No product cutover.",
        "- No shared app ownership moved.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (snapshot.get("checks") or {}).items())
    lines.extend(["", "## Runtime Hashes", ""])
    lines.extend(
        [
            f"- selected_repair_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('selected_repair_ladder_hash')}`",
            f"- exact_stop_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('exact_stop_ladder_hash')}`",
            f"- exhausted_ladder_hash: `{snapshot.get('scenario_hashes', {}).get('exhausted_ladder_hash')}`",
        ]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    contract = load_serviceability_governs_contract()
    contract_lane_order = serviceability_contract_lane_order()
    result_fields = {field.name for field in fields(ServiceabilityGovernsResult)}

    selected_repair_result = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state(current_utilisation=1.2)),
        evaluate_candidate=_bottom_accepting_evaluator,
    )
    repeated_selected_repair_result = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state(current_utilisation=1.2)),
        evaluate_candidate=_bottom_accepting_evaluator,
    )
    exact_stop_result = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state(current_utilisation=0.92)),
        evaluate_candidate=_rejecting_evaluator,
    )
    exhausted_result = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(
            base_state=_base_state(
                current_utilisation=1.2,
                blockers=["geometry limits reached", "detailing limits reached"],
            )
        ),
        evaluate_candidate=_rejecting_evaluator,
    )

    selected_trace = _trace_by_lane(selected_repair_result)
    exhausted_trace = _trace_by_lane(exhausted_result)
    exact_trace = _trace_by_lane(exact_stop_result)

    checks = {
        "contract_loads": bool(contract),
        "contract_family_id": (contract.get("family_identity") or {}).get("family_id") == "SERVICEABILITY_GOVERNS",
        "runtime_lane_order_equals_contract": contract_lane_order == EXPECTED_LANE_ORDER,
        "required_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "selected_repair_uses_bottom_reinforcement_lane": selected_repair_result.selected_strategy_lane == "BOTTOM_REINFORCEMENT_INCREASE",
        "selected_repair_has_candidate_update": bool((selected_repair_result.selected_recommendation or {}).get("updates")),
        "selected_repair_exact_stop_proven": selected_repair_result.exact_stop_proof.get("allowed") is True,
        "depth_restart_rule_represented": tuple((exhausted_trace.get("DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get("restart_after") or ()) == ("BOTTOM_REINFORCEMENT_INCREASE",),
        "width_restart_rule_represented": tuple((exhausted_trace.get("WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") or {}).get("restart_after") or ()) == ("BOTTOM_REINFORCEMENT_INCREASE",),
        "combined_lane_reached_when_prior_lanes_fail": "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH" in exhausted_trace,
        "exact_stop_selected_for_compliant_current_state": exact_stop_result.selected_strategy_lane == "EXACT_STOP" and (exact_trace.get("EXACT_STOP") or {}).get("accepted") is True,
        "exhausted_selected_when_no_valid_repair": exhausted_result.selected_strategy_lane == "EXHAUSTED",
        "exhausted_has_specific_blocker_evidence": bool(exhausted_result.exhausted_proof.get("specific_blockers")),
        "ranking_follows_contract_order": tuple(ranking_criteria()) == EXPECTED_RANKING and tuple(selected_repair_result.ranking_evidence.get("criteria") or ()) == EXPECTED_RANKING,
        "candidate_evaluation_boundary_used": bool((selected_repair_result.candidate_repairs or ({},))[0].get("evaluation_hash")),
        "ladder_hash_stable": selected_repair_result.ladder_hash == repeated_selected_repair_result.ladder_hash,
        "ownership_proof_keeps_shared_systems_out": selected_repair_result.ownership_proof.get("shared_system_ownership_not_entered") is True,
        "runtime_has_no_page_or_shared_app_imports": not _forbidden_imports(RUNTIME_PATH) and not _forbidden_source_hits(RUNTIME_PATH),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "serviceability_governs_ladder_runtime_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_lane_order": contract_lane_order,
        "checks": checks,
        "forbidden_imports": _forbidden_imports(RUNTIME_PATH),
        "forbidden_source_hits": _forbidden_source_hits(RUNTIME_PATH),
        "scenario_hashes": {
            "selected_repair_ladder_hash": selected_repair_result.ladder_hash,
            "repeat_selected_repair_ladder_hash": repeated_selected_repair_result.ladder_hash,
            "exact_stop_ladder_hash": exact_stop_result.ladder_hash,
            "exhausted_ladder_hash": exhausted_result.ladder_hash,
        },
        "scenario_summaries": {
            "selected_repair": {
                "status": selected_repair_result.status,
                "selected_strategy_lane": selected_repair_result.selected_strategy_lane,
                "selected_recommendation": selected_repair_result.selected_recommendation,
                "ranking_evidence": selected_repair_result.ranking_evidence,
                "bottom_lane_trace": selected_trace.get("BOTTOM_REINFORCEMENT_INCREASE"),
            },
            "exact_stop": {
                "status": exact_stop_result.status,
                "selected_strategy_lane": exact_stop_result.selected_strategy_lane,
                "exact_stop_proof": exact_stop_result.exact_stop_proof,
            },
            "exhausted": {
                "status": exhausted_result.status,
                "selected_strategy_lane": exhausted_result.selected_strategy_lane,
                "exhausted_reason": exhausted_result.exhausted_reason,
                "exhausted_proof": exhausted_result.exhausted_proof,
            },
        },
        "snapshot_hash": stable_serviceability_candidate_hash(
            {
                "contract_lane_order": contract_lane_order,
                "scenario_hashes": {
                    "selected_repair_ladder_hash": selected_repair_result.ladder_hash,
                    "exact_stop_ladder_hash": exact_stop_result.ladder_hash,
                    "exhausted_ladder_hash": exhausted_result.ladder_hash,
                },
                "checks": checks,
            }
        ),
        "failures": failures,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_ladder_runtime_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_ladder_runtime_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)

    print(f"{snapshot['status']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
