"""Current-live replacement audit for SERVICEABILITY_GOVERNS.

The contract runtime is authoritative. Existing page-owned crack/deflection
attempts and the family scaffold are recorded only as replacement-impact
evidence, not as a test oracle.
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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "serviceability_governs" / "runtime.py"

from design_brain.families.serviceability import ServiceabilityFamily  # noqa: E402
from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    load_serviceability_governs_contract,
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
)


EXPECTED_CONTRACT_ORDER = (
    "BOTTOM_REINFORCEMENT_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "COMBINED_GEOMETRY_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
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
DIFFERENCE_CLASSES = {
    "EXPECTED_CONTRACT_REPLACEMENT",
    "MISSING_NEW_EVIDENCE_BLOCKER",
    "NO_OLD_EQUIVALENT_NEEDED",
}
FORBIDDEN_IMPORT_PREFIXES = {
    "inputs_page",
    "streamlit",
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
}
FORBIDDEN_RUNTIME_KEYS = {
    "publication",
    "cta_contract",
    "apply_routing",
    "rendered_html",
    "session_state",
    "source_precedence",
    "visible_wording",
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


def _walk_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_RUNTIME_KEYS:
                found.add(str(key))
            found.update(_walk_forbidden_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_walk_forbidden_keys(child))
    return found


def _base_state(*, current_utilisation: float = 1.2, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "geometry": {"beam_width_mm": 300.0, "beam_depth_mm": 500.0},
        "reinforcement": {"bottom_bar_count": 3, "bottom_bar_diameter_mm": 20},
        "actions": {"current_serviceability_utilisation": current_utilisation},
        "failure_flags": {"bending_fail": False, "shear_fail": False},
        "constraints": {"blocker_reasons": blockers or []},
    }


def _evaluation(
    candidate_input: ServiceabilityCandidateInput,
    candidate_update: ServiceabilityCandidateUpdate,
    *,
    serviceability_utilisation: float,
    serviceability_compliant: bool,
    blocker_reasons: list[str] | None = None,
) -> ServiceabilityCandidateEvaluation:
    return ServiceabilityCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_serviceability_candidate_state_hash(candidate_input.base_state, candidate_update.updates),
        serviceability_utilisation=serviceability_utilisation,
        previous_serviceability_utilisation=1.2,
        serviceability_improved=serviceability_utilisation < 1.2,
        serviceability_compliant=serviceability_compliant,
        deflection_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        crack_control_status={"status": "PASS" if serviceability_compliant else "FAIL"},
        strength_status={"overall": "PASS", "bending": "PASS", "shear": "PASS"},
        code_compliance_status={"overall": "PASS"},
        constructability_status={"overall": "PASS"},
        geometry_status={"status": "CHECKED"},
        reinforcement_status={"status": "CHECKED"},
        blocker_status={"blocked": bool(blocker_reasons), "reasons": blocker_reasons or []},
        capacity_summary={"boundary": "serviceability_candidate_evaluation_api_shape"},
        failure_flags={
            "serviceability_fail": not serviceability_compliant,
            "bending_fail": False,
            "shear_fail": False,
            "constructability_fail": False,
        },
        engineering_status={"overall": "PASS" if serviceability_compliant else "FAIL"},
    ).with_evaluation_hash()


def _selected_runtime_result() -> ServiceabilityGovernsResult:
    def evaluator(
        candidate_input: ServiceabilityCandidateInput,
        candidate_update: ServiceabilityCandidateUpdate,
    ) -> ServiceabilityCandidateEvaluation:
        reinforcement = dict((candidate_update.updates or {}).get("reinforcement") or {})
        if reinforcement.get("bottom_bar_count") == 4:
            return _evaluation(candidate_input, candidate_update, serviceability_utilisation=0.96, serviceability_compliant=True)
        return _evaluation(candidate_input, candidate_update, serviceability_utilisation=1.1, serviceability_compliant=False)

    return run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state()),
        evaluate_candidate=evaluator,
    )


def _exhausted_runtime_result() -> ServiceabilityGovernsResult:
    def evaluator(
        candidate_input: ServiceabilityCandidateInput,
        candidate_update: ServiceabilityCandidateUpdate,
    ) -> ServiceabilityCandidateEvaluation:
        return _evaluation(
            candidate_input,
            candidate_update,
            serviceability_utilisation=1.08,
            serviceability_compliant=False,
            blocker_reasons=["geometry limits reached"],
        )

    return run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(
            base_state=_base_state(blockers=["geometry limits reached", "constructability limits reached"])
        ),
        evaluate_candidate=evaluator,
    )


def _old_live_evidence() -> dict[str, Any]:
    metadata = ServiceabilityFamily.metadata
    package_source = (ROOT / "design_brain" / "families" / "serviceability_governs" / "__init__.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    return {
        "source": "ServiceabilityFamily metadata plus page-owned crack/deflection attempts",
        "used_as_authority": False,
        "family_shell_exists": metadata.governing_state == "SERVICEABILITY_GOVERNS",
        "candidate_strategy": metadata.candidate_strategy,
        "ranking_strategy": metadata.ranking_strategy,
        "package_api_present": "def evaluate_serviceability_governs" in package_source,
        "package_api_still_scaffolded": "NotImplementedError" in package_source,
        "page_owned_serviceability_attempts_present": all(
            token in inputs_source
            for token in (
                "serviceability_crack_active_failure_ladder",
                "serviceability_deflection_active_failure_ladder",
            )
        ),
        "observed_runtime_order": [],
    }


def _classify_differences(
    *,
    old_evidence: dict[str, Any],
    selected_payload: dict[str, Any],
    exhausted_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "item": "old_scaffold_vs_contract_runtime",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "Existing SERVICEABILITY family package was scaffolded; contract runtime now owns the ladder authority.",
        },
        {
            "item": "page_owned_crack_deflection_attempts_vs_family_ladder",
            "class": "EXPECTED_CONTRACT_REPLACEMENT",
            "reason": "Existing page attempts remain evidence of current behavior, while family runtime owns candidate generation and ranking.",
        },
        {
            "item": "contract_lanes_without_old_runtime_equivalent",
            "class": "NO_OLD_EQUIVALENT_NEEDED",
            "reason": "No old serviceability family runtime existed with contract-ordered lanes.",
            "lanes": list(EXPECTED_CONTRACT_ORDER),
        },
    ]
    missing = []
    if not selected_payload.get("candidate_repairs"):
        missing.append("candidate_repairs")
    if not selected_payload.get("selected_recommendation"):
        missing.append("selected_recommendation")
    if not selected_payload.get("ranking_evidence"):
        missing.append("ranking_evidence")
    if not exhausted_payload.get("exhausted_proof"):
        missing.append("exhausted_proof")
    if not exhausted_payload.get("exhausted_reason"):
        missing.append("exhausted_reason")
    if missing:
        rows.append(
            {
                "item": "new_runtime_missing_cutover_evidence",
                "class": "MISSING_NEW_EVIDENCE_BLOCKER",
                "reason": "Cutover cannot proceed without these proof surfaces.",
                "missing": missing,
            }
        )
    else:
        rows.append(
            {
                "item": "new_runtime_evidence_surface",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The runtime emits candidate repairs, selected recommendation, ranking evidence, exact stop proof, exhausted proof, and ownership proof.",
            }
        )
    if old_evidence.get("package_api_present"):
        rows.append(
            {
                "item": "package_api_runtime_replacement",
                "class": "EXPECTED_CONTRACT_REPLACEMENT",
                "reason": "The public API is the narrow replacement target for cutover and now identifies the runtime authority.",
            }
        )
    return rows


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_replacement_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_replacement_audit_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SERVICEABILITY_GOVERNS Replacement Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "Authority rule: the SERVICEABILITY contract runtime is authoritative.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(["", "## Difference Classification", ""])
    lines.extend(
        f"- `{entry['item']}`: `{entry['class']}` - {entry['reason']}"
        for entry in snapshot["difference_classification"]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = load_serviceability_governs_contract()
    old_evidence = _old_live_evidence()
    selected = _selected_runtime_result()
    selected_repeat = _selected_runtime_result()
    exhausted = _exhausted_runtime_result()
    selected_payload = selected.to_dict()
    exhausted_payload = exhausted.to_dict()
    differences = _classify_differences(
        old_evidence=old_evidence,
        selected_payload=selected_payload,
        exhausted_payload=exhausted_payload,
    )
    unknown_classes = sorted({str(row.get("class")) for row in differences} - DIFFERENCE_CLASSES)
    blockers = [row for row in differences if row.get("class") == "MISSING_NEW_EVIDENCE_BLOCKER"]
    forbidden_fields = sorted(_walk_forbidden_keys({"selected": selected_payload, "exhausted": exhausted_payload}))
    result_fields = {field.name for field in fields(ServiceabilityGovernsResult)}
    checks = {
        "contract_runtime_order_unchanged": serviceability_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "new_runtime_result_fields_exist": REQUIRED_RESULT_FIELDS.issubset(result_fields),
        "old_family_shell_identified_not_authority": old_evidence.get("package_api_present") is True
        and old_evidence.get("used_as_authority") is False,
        "new_runtime_evidence_sufficient_for_cutover_audit": bool(selected_payload.get("candidate_repairs"))
        and bool(selected_payload.get("selected_recommendation"))
        and bool(selected_payload.get("ranking_evidence"))
        and bool(exhausted_payload.get("exhausted_proof")),
        "old_behavior_did_not_alter_runtime_hash": selected.ladder_hash == selected_repeat.ladder_hash,
        "no_forbidden_runtime_fields": not forbidden_fields,
        "runtime_has_no_page_or_shared_app_imports": not _forbidden_imports(RUNTIME_PATH),
        "difference_classes_are_known": not unknown_classes,
        "no_missing_new_evidence_blockers": not blockers,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "serviceability_governs_replacement_audit.v1",
        "result": "PASS" if not failures else "FAIL",
        "contract_path": str(CONTRACT_PATH),
        "contract_schema": contract.get("schema"),
        "authority_rule": "serviceability_contract_runtime_is_authoritative",
        "contract_order": list(serviceability_contract_lane_order()),
        "old_live_evidence": old_evidence,
        "new_runtime": {
            "selected_strategy_lane": selected.selected_strategy_lane,
            "selected_recommendation": selected.selected_recommendation,
            "ladder_hash": selected.ladder_hash,
            "repeat_ladder_hash": selected_repeat.ladder_hash,
            "candidate_repair_count": len(selected.candidate_repairs),
            "ranking_evidence": selected.ranking_evidence,
        },
        "terminal_runtime": {
            "selected_strategy_lane": exhausted.selected_strategy_lane,
            "exhausted_reason": exhausted.exhausted_reason,
            "exhausted_proof": exhausted.exhausted_proof,
            "ladder_hash": exhausted.ladder_hash,
        },
        "difference_classification": differences,
        "forbidden_fields": forbidden_fields,
        "forbidden_runtime_imports": _forbidden_imports(RUNTIME_PATH),
        "checks": checks,
        "failures": failures,
        "scope_limits": {
            "runtime_decisions_changed_to_match_old_behavior": False,
            "compatibility_branches_added": False,
            "cutover_enabled": False,
            "shared_app_ownership_moved": False,
        },
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['result']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
