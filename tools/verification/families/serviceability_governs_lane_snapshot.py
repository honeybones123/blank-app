from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    contract_hash,
    exact_stop_rules,
    exhausted_rules,
    lane_proof_policies,
    repair_ladder,
    serviceability_contract_lane_order,
    shared_exclusions,
    strength_protection,
)
from design_brain.serviceability_candidate_evaluation import (  # noqa: E402
    ServiceabilityCandidateEvaluation,
    ServiceabilityCandidateInput,
    ServiceabilityCandidateUpdate,
    build_serviceability_candidate_state_hash,
    stable_serviceability_candidate_hash,
)


EXPECTED_LANE_ORDER = [
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
]
REQUIRED_SHARED_EXCLUSIONS = {
    "family selection",
    "family arbitration",
    "publication",
    "CTA generation",
    "CTA rendering",
    "apply routing",
    "one-click orchestration",
    "session state",
    "UI rendering",
    "source precedence",
    "visible wording",
}
FORBIDDEN_RUNTIME_IMPORT_ROOTS = {"inputs_page", "streamlit"}


def _base_state() -> dict[str, Any]:
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
        "materials": {
            "concrete_strength_mpa": 32.0,
            "steel_strength_mpa": 500.0,
        },
        "actions": {
            "service_moment_knm": 260.0,
            "sustained_load_knm": 180.0,
        },
        "constraints": {
            "maximum_depth_mm": 650.0,
            "maximum_width_mm": 450.0,
            "minimum_bottom_bar_count": 2,
        },
    }


def _evaluation_boundary_sample(
    update: dict[str, Any],
    *,
    serviceability_utilisation: float,
    previous_utilisation: float,
    serviceability_compliant: bool,
    bending_fail: bool,
    shear_fail: bool,
    constructability_fail: bool = False,
    blocker_reasons: list[str] | None = None,
) -> dict[str, Any]:
    boundary_input = ServiceabilityCandidateInput(base_state=_base_state())
    boundary_update = ServiceabilityCandidateUpdate(updates=update)
    candidate_state_hash = build_serviceability_candidate_state_hash(
        boundary_input.base_state,
        boundary_update.updates,
    )
    evaluation = ServiceabilityCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=boundary_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        serviceability_utilisation=serviceability_utilisation,
        previous_serviceability_utilisation=previous_utilisation,
        serviceability_improved=serviceability_utilisation < previous_utilisation,
        serviceability_compliant=serviceability_compliant,
        deflection_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        crack_control_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        strength_status={
            "overall": "FAIL" if bending_fail or shear_fail else "PASS",
            "bending": "FAIL" if bending_fail else "PASS",
            "shear": "FAIL" if shear_fail else "PASS",
        },
        code_compliance_status={"overall": "PASS"},
        constructability_status={"overall": "FAIL" if constructability_fail else "PASS"},
        geometry_status={"status": "CHECKED"},
        reinforcement_status={"status": "CHECKED"},
        blocker_status={
            "blocked": bool(blocker_reasons),
            "reasons": blocker_reasons or [],
        },
        capacity_summary={
            "serviceability_utilisation": serviceability_utilisation,
            "previous_serviceability_utilisation": previous_utilisation,
        },
        failure_flags={
            "serviceability_fail": not serviceability_compliant,
            "bending_fail": bending_fail,
            "shear_fail": shear_fail,
            "constructability_fail": constructability_fail,
        },
        engineering_status={"overall": "PASS" if serviceability_compliant and not bending_fail and not shear_fail else "FAIL"},
    ).with_evaluation_hash()
    repeated = ServiceabilityCandidateEvaluation(
        input_hash=boundary_input.input_hash,
        update_hash=boundary_update.update_hash,
        candidate_state_hash=candidate_state_hash,
        serviceability_utilisation=serviceability_utilisation,
        previous_serviceability_utilisation=previous_utilisation,
        serviceability_improved=serviceability_utilisation < previous_utilisation,
        serviceability_compliant=serviceability_compliant,
        deflection_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        crack_control_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        strength_status={
            "overall": "FAIL" if bending_fail or shear_fail else "PASS",
            "bending": "FAIL" if bending_fail else "PASS",
            "shear": "FAIL" if shear_fail else "PASS",
        },
        code_compliance_status={"overall": "PASS"},
        constructability_status={"overall": "FAIL" if constructability_fail else "PASS"},
        geometry_status={"status": "CHECKED"},
        reinforcement_status={"status": "CHECKED"},
        blocker_status={
            "blocked": bool(blocker_reasons),
            "reasons": blocker_reasons or [],
        },
        capacity_summary={
            "serviceability_utilisation": serviceability_utilisation,
            "previous_serviceability_utilisation": previous_utilisation,
        },
        failure_flags={
            "serviceability_fail": not serviceability_compliant,
            "bending_fail": bending_fail,
            "shear_fail": shear_fail,
            "constructability_fail": constructability_fail,
        },
        engineering_status={"overall": "PASS" if serviceability_compliant and not bending_fail and not shear_fail else "FAIL"},
    ).with_evaluation_hash()
    return {
        "input_hash": boundary_input.input_hash,
        "update_hash": boundary_update.update_hash,
        "candidate_state_hash": candidate_state_hash,
        "evaluation_hash": evaluation.evaluation_hash,
        "repeat_evaluation_hash": repeated.evaluation_hash,
        "hashes_stable": evaluation.evaluation_hash == repeated.evaluation_hash,
        "evaluation": evaluation.to_dict(),
    }


def _accepted_before_ranking(evaluation: dict[str, Any]) -> bool:
    flags = dict(evaluation.get("failure_flags") or {})
    return (
        bool(evaluation.get("serviceability_improved"))
        and bool(evaluation.get("serviceability_compliant"))
        and not flags.get("bending_fail")
        and not flags.get("shear_fail")
        and not flags.get("constructability_fail")
    )


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_lane_snapshot_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_lane_snapshot_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SERVICEABILITY_GOVERNS Lane Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- {key}: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
                "## Snapshot",
                "",
                f"- contract_hash: `{snapshot['contract_hash']}`",
                f"- snapshot_hash: `{snapshot['snapshot_hash']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    lane_order = list(serviceability_contract_lane_order())
    policies = lane_proof_policies()
    ladder = repair_ladder()
    shared = set(shared_exclusions())
    strength = strength_protection()
    exact = exact_stop_rules()
    exhausted = exhausted_rules()

    case_a = _evaluation_boundary_sample(
        {"reinforcement": {"bottom_bar_count": 4}},
        serviceability_utilisation=0.96,
        previous_utilisation=1.14,
        serviceability_compliant=True,
        bending_fail=False,
        shear_fail=False,
    )
    case_b = _evaluation_boundary_sample(
        {"geometry": {"beam_depth_mm": 650.0}},
        serviceability_utilisation=0.94,
        previous_utilisation=1.12,
        serviceability_compliant=True,
        bending_fail=True,
        shear_fail=False,
    )
    case_c = _evaluation_boundary_sample(
        {"geometry": {"beam_width_mm": 450.0}},
        serviceability_utilisation=0.93,
        previous_utilisation=1.1,
        serviceability_compliant=True,
        bending_fail=False,
        shear_fail=True,
    )
    exhausted_case = _evaluation_boundary_sample(
        {"terminal": {"attempted": "all_lanes"}},
        serviceability_utilisation=1.08,
        previous_utilisation=1.15,
        serviceability_compliant=False,
        bending_fail=False,
        shear_fail=False,
        blocker_reasons=["geometry limits reached", "detailing limits reached"],
    )

    restart_after = dict(ladder.get("restart_after") or {})
    repair_validity = dict(policies.get("repair_validity") or {})
    terminal = dict(policies.get("terminal") or {})
    lane_policy_order = list((policies.get("ladder_order") or {}).get("expected") or [])

    checks = {
        "contract_lane_order_exact": lane_order == EXPECTED_LANE_ORDER,
        "lane_policy_order_exact": lane_policy_order == EXPECTED_LANE_ORDER,
        "depth_restarts_reinforcement_search": restart_after.get("DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") == ["BOTTOM_REINFORCEMENT_INCREASE"],
        "width_restarts_reinforcement_search": restart_after.get("WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH") == ["BOTTOM_REINFORCEMENT_INCREASE"],
        "case_a_rankable": _accepted_before_ranking(case_a["evaluation"]) is True,
        "case_b_rejected_before_ranking": _accepted_before_ranking(case_b["evaluation"]) is False,
        "case_c_rejected_before_ranking": _accepted_before_ranking(case_c["evaluation"]) is False,
        "repair_validity_policies_present": {"case_a", "case_b", "case_c"}.issubset(set(repair_validity)),
        "strength_protection_rejects_bending_and_shear_failures": {
            "bending failure created",
            "shear failure created",
        }.issubset(set(strength.get("invalid_before_ranking") or [])),
        "exact_stop_requires_serviceability_and_strength": {
            "serviceability compliant",
            "strength compliant",
        }.issubset(set(exact.get("allowed_when") or [])),
        "terminal_policy_has_exact_and_exhausted_rules": bool(terminal.get("exact_stop_allowed_when")) and bool(terminal.get("exhausted_requires")),
        "exhausted_requires_all_lanes_and_specific_blocker": {
            "all ladder branches attempted",
            "specific blocker exists",
        }.issubset(set(exhausted.get("requires") or [])),
        "exhausted_case_has_specific_blockers": bool(exhausted_case["evaluation"]["blocker_status"]["reasons"]),
        "shared_exclusions_preserved": REQUIRED_SHARED_EXCLUSIONS.issubset(shared),
        "candidate_hashes_stable": all(
            sample["hashes_stable"] for sample in (case_a, case_b, case_c, exhausted_case)
        ),
    }
    failures = [key for key, value in checks.items() if not value]
    snapshot_payload = {
        "lane_order": lane_order,
        "lane_policy_order": lane_policy_order,
        "restart_after": restart_after,
        "case_a": case_a,
        "case_b": case_b,
        "case_c": case_c,
        "exhausted_case": exhausted_case,
    }
    snapshot = {
        "schema": "serviceability_governs_lane_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_hash": contract_hash(),
        "checks": checks,
        "failures": failures,
        "snapshot_payload": snapshot_payload,
        "forbidden_runtime_import_roots": sorted(FORBIDDEN_RUNTIME_IMPORT_ROOTS),
        "snapshot_hash": stable_serviceability_candidate_hash(snapshot_payload),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SERVICEABILITY_GOVERNS lane snapshot FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SERVICEABILITY_GOVERNS lane snapshot PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
