"""Current-live replacement audit for SHEAR_FAIL_GOVERNS.

The contract runtime is authoritative. Old live behaviour is recorded only as
replacement-impact evidence and is not used as a test oracle.
"""

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

from design_brain.families.shear_fail import ShearFailFamily  # noqa: E402
from design_brain.families.shear_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    load_shear_fail_governs_contract,
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


EXPECTED_CONTRACT_ORDER = (
    "SPACING_REDUCTION",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
    "NO_VALID_REPAIR",
)
DIFFERENCE_CLASSES = {
    "EXPECTED_CONTRACT_REPLACEMENT",
    "MISSING_NEW_EVIDENCE_BLOCKER",
    "UNEXPLAINED_REPLACEMENT_RISK",
    "NO_OLD_EQUIVALENT_NEEDED",
}
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
FORBIDDEN_KEYS = {
    "apply_routing",
    "button_contract",
    "button_label",
    "publication",
    "published_item",
    "rendered_button",
    "rendered_html",
    "session",
    "session_state",
    "source_precedence",
    "ui",
    "visible_wording",
}
FORBIDDEN_IMPORT_PREFIXES = {
    "design_brain.families.bending",
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
    "inputs_page",
    "streamlit",
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
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES):
            blocked.append(imported)
    return sorted(set(blocked))


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_KEYS:
                found.add(str(key))
            found.update(_walk_forbidden(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden(child))
    return found


def _base_state(*, current_util: float = 1.18, constraints_prohibit: bool = False) -> dict[str, Any]:
    return {
        "b": 400.0,
        "D": 600.0,
        "s_lig": 300.0,
        "lig_d": 10,
        "lig_legs": 2,
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
    candidate_input: ShearCandidateInput,
    candidate_update: ShearCandidateUpdate,
    *,
    shear_utilisation: float,
    status: str,
) -> ShearCandidateEvaluation:
    return ShearCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_candidate_state_hash(candidate_input.base_state, candidate_update.updates),
        shear_utilisation=shear_utilisation,
        previous_shear_utilisation=1.18,
        utilisation_improved=shear_utilisation < 1.18,
        code_compliance_status={"overall": status},
        constructability_status={"overall": status},
        spacing_status={"status": status},
        bar_size_status={"status": status},
        leg_count_status={"status": status},
        geometry_status={"status": status},
        capacity_summary={"boundary": "shear_candidate_evaluation_api_shape"},
        failure_flags={"shear_fail": shear_utilisation > 1.0},
        engineering_status={"overall": status, "target_band_status": "TARGET" if 0.85 <= shear_utilisation <= 1.0 else "FAIL"},
    ).with_evaluation_hash()


def _authoritative_runtime_result() -> dict[str, Any]:
    calls: list[str] = []

    def evaluator(candidate_input: ShearCandidateInput, candidate_update: ShearCandidateUpdate) -> ShearCandidateEvaluation:
        reinforcement = dict((candidate_update.updates or {}).get("reinforcement") or {})
        lane_hint = "UNKNOWN"
        if "ligature_spacing_mm" in reinforcement and not {"ligature_diameter_mm", "ligature_leg_count"} & set(reinforcement):
            lane_hint = "SPACING_REDUCTION"
        elif "ligature_diameter_mm" in reinforcement and "ligature_leg_count" not in reinforcement:
            lane_hint = "BAR_SIZE_OR_RESET"
        elif "ligature_leg_count" in reinforcement:
            lane_hint = "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH"
        calls.append(lane_hint)
        if reinforcement.get("ligature_spacing_mm") == 100:
            return _evaluation(candidate_input, candidate_update, shear_utilisation=0.93, status="PASS")
        return _evaluation(candidate_input, candidate_update, shear_utilisation=1.18, status="FAIL")

    result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(),
        evaluate_candidate=evaluator,
    )
    return {
        "result": result,
        "payload": result.to_dict(),
        "call_count": len(calls),
        "call_hints": calls,
    }


def _terminal_runtime_result() -> dict[str, Any]:
    def evaluator(candidate_input: ShearCandidateInput, candidate_update: ShearCandidateUpdate) -> ShearCandidateEvaluation:
        return _evaluation(candidate_input, candidate_update, shear_utilisation=1.18, status="FAIL")

    result = run_shear_fail_governs_ladder_runtime(
        base_state=_base_state(constraints_prohibit=True),
        evaluate_candidate=evaluator,
    )
    return {"result": result, "payload": result.to_dict()}


def _infer_old_lane(spec: dict[str, Any]) -> str:
    step = spec.get("contract_step")
    strategy = str(spec.get("strategy") or "").lower()
    if step == 1 or "reduce spacing" in strategy:
        return "SPACING_REDUCTION"
    if step == 2 or "diameter" in strategy:
        return "BAR_SIZE_INCREASE"
    if step == 3 or "width" in strategy:
        return "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH"
    return f"UNKNOWN:{step or 'missing_step'}"


def _current_live_evidence() -> dict[str, Any]:
    family = ShearFailFamily()
    result = family.contracted_repair_ladder_specs(_base_state(), geometry_locked=False)
    specs = [dict(spec) for spec in result.get("specs") or []]
    lane_sequence = [_infer_old_lane(spec) for spec in specs]
    observed_order: list[str] = []
    for lane in lane_sequence:
        if lane not in observed_order:
            observed_order.append(lane)
    return {
        "source": "ShearFailFamily.contracted_repair_ladder_specs",
        "used_as_authority": False,
        "candidate_count": len(specs),
        "observed_lane_order": observed_order,
        "spacing_values_tried": list(result.get("spacing_values_tried") or []),
        "lig_diameters_tried": list(result.get("lig_diameters_tried") or []),
        "widths_tried": list(result.get("widths_tried") or []),
        "stop_reason_if_no_candidate": result.get("stop_reason_if_no_candidate"),
    }


def _classify_differences(
    *,
    old_evidence: dict[str, Any],
    runtime_payload: dict[str, Any],
    terminal_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    old_order = list(old_evidence.get("observed_lane_order") or [])
    if tuple(old_order) != EXPECTED_CONTRACT_ORDER:
        rows.append(
            {
                "item": "old_live_ladder_order_vs_contract_runtime_order",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The new SHEAR contract runtime is authoritative; old spacing/diameter/width ordering is impact evidence only.",
                "old_order": old_order,
                "new_order": list(EXPECTED_CONTRACT_ORDER),
            }
        )
    old_missing = [lane for lane in EXPECTED_CONTRACT_ORDER if lane not in old_order]
    if old_missing:
        rows.append(
            {
                "item": "contract_lanes_without_old_live_equivalent",
                "class": "NO_OLD_EQUIVALENT_NEEDED",
                "reason": "Depth reset, leg-count reset, and terminal proof lanes are contract-owned additions not exposed by the current live repair ladder.",
                "lanes": old_missing,
            }
        )

    missing_evidence = []
    if not runtime_payload.get("candidate_repairs"):
        missing_evidence.append("candidate_repairs")
    if not runtime_payload.get("selected_recommendation"):
        missing_evidence.append("selected_recommendation")
    if not runtime_payload.get("ranking_proof"):
        missing_evidence.append("ranking_proof")
    if not terminal_payload.get("exhausted_reason"):
        missing_evidence.append("exhausted_reason")
    if not terminal_payload.get("no_valid_repair_proof"):
        missing_evidence.append("no_valid_repair_proof")
    if missing_evidence:
        rows.append(
            {
                "item": "new_runtime_missing_cutover_evidence",
                "class": "MISSING_NEW_EVIDENCE_BLOCKER",
                "reason": "Cutover cannot proceed without these proof surfaces.",
                "missing": missing_evidence,
            }
        )
    else:
        rows.append(
            {
                "item": "new_runtime_evidence_surface",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The runtime emits candidate repairs, selected recommendation, ranking proof, terminal proof, repair proof, and proof-only CTA intent.",
            }
        )
    rows.append(
        {
            "item": "old_cta_publication_apply_ownership_vs_new_cta_intent_proof",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "Old product path still owns CTA/publication/apply. The new runtime exposes only non-product-driving CTA intent proof.",
        }
    )
    return rows


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_replacement_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SHEAR_FAIL_GOVERNS Replacement Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "Authority rule: the new SHEAR contract runtime is authoritative.",
        "Old live behaviour is replacement-impact evidence only.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(
        [
            "",
            "## Runtime Order",
            "",
            "```text",
            " -> ".join(snapshot["new_runtime"]["contract_order"]),
            "```",
            "",
            "## Current Live Impact Evidence",
            "",
            "```text",
            " -> ".join(snapshot["old_live_evidence"]["observed_lane_order"]),
            "```",
            "",
            "## Difference Classification",
            "",
        ]
    )
    lines.extend(
        f"- `{entry['item']}`: `{entry['class']}` - {entry['reason']}"
        for entry in snapshot["difference_classification"]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = load_shear_fail_governs_contract()
    first = _authoritative_runtime_result()
    old_evidence = _current_live_evidence()
    second = _authoritative_runtime_result()
    terminal = _terminal_runtime_result()

    runtime_payload = first["payload"]
    terminal_payload = terminal["payload"]
    differences = _classify_differences(
        old_evidence=old_evidence,
        runtime_payload=runtime_payload,
        terminal_payload=terminal_payload,
    )
    classes = {str(row.get("class")) for row in differences}
    unknown_classes = sorted(classes - DIFFERENCE_CLASSES)
    blockers = [row for row in differences if row.get("class") == "MISSING_NEW_EVIDENCE_BLOCKER"]
    risks = [row for row in differences if row.get("class") == "UNEXPLAINED_REPLACEMENT_RISK"]
    forbidden_fields = sorted(_walk_forbidden({"runtime": runtime_payload, "terminal": terminal_payload}))
    required_fields = {field.name for field in fields(ShearFailGovernsResult)}
    runtime_imports = _forbidden_imports(RUNTIME_PATH)

    checks = {
        "contract_runtime_order_unchanged": shear_fail_governs_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "new_runtime_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(required_fields),
        "new_runtime_evidence_sufficient_for_cutover_audit": bool(runtime_payload.get("candidate_repairs"))
        and bool(runtime_payload.get("selected_recommendation"))
        and bool(runtime_payload.get("ranking_proof"))
        and bool(runtime_payload.get("repair_reason_proof"))
        and bool(runtime_payload.get("cta_intent_proof")),
        "restart_behavior_evidence_exists": any(
            row.get("restart_evidence") for row in terminal_payload.get("ladder_trace") or []
        ),
        "ranking_proof_exists": bool(runtime_payload.get("ranking_proof")),
        "terminal_proof_exists": bool(terminal_payload.get("exhausted_reason"))
        and bool(terminal_payload.get("no_valid_repair_proof")),
        "old_behavior_did_not_alter_runtime_hash": first["result"].ladder_hash == second["result"].ladder_hash,
        "no_forbidden_runtime_fields": not forbidden_fields,
        "runtime_has_no_page_or_bending_imports": not runtime_imports,
        "difference_classes_are_known": not unknown_classes,
        "no_missing_new_evidence_blockers": not blockers,
        "no_unexplained_replacement_risk": not risks,
    }
    failures = [key for key, passed in checks.items() if not passed]

    snapshot = {
        "schema": "shear_fail_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_schema": contract.get("schema"),
        "authority_rule": "new_shear_contract_runtime_is_authoritative",
        "new_runtime": {
            "contract_order": list(shear_fail_governs_contract_lane_order()),
            "selected_strategy_lane": runtime_payload.get("selected_strategy_lane"),
            "selected_recommendation": runtime_payload.get("selected_recommendation"),
            "ladder_hash": runtime_payload.get("ladder_hash"),
            "repeat_ladder_hash": second["result"].ladder_hash,
            "candidate_repair_count": len(runtime_payload.get("candidate_repairs") or []),
            "ranking_proof": runtime_payload.get("ranking_proof"),
            "cta_intent_proof": runtime_payload.get("cta_intent_proof"),
        },
        "terminal_runtime": {
            "selected_strategy_lane": terminal_payload.get("selected_strategy_lane"),
            "exhausted_reason": terminal_payload.get("exhausted_reason"),
            "no_valid_repair_proof": terminal_payload.get("no_valid_repair_proof"),
            "ladder_hash": terminal_payload.get("ladder_hash"),
        },
        "old_live_evidence": old_evidence,
        "difference_classification": differences,
        "forbidden_fields": forbidden_fields,
        "forbidden_runtime_imports": runtime_imports,
        "checks": checks,
        "failures": failures,
        "scope_limits": {
            "runtime_decisions_changed_to_match_old_behavior": False,
            "compatibility_branches_added": False,
            "cutover_enabled": False,
            "cta_publication_apply_ui_session_moved": False,
            "bending_touched": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    print(f"{snapshot['result']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
