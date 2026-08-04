"""Cutover implementation verifier for SERVICEABILITY_GOVERNS."""

from __future__ import annotations

import ast
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
RUNTIME_PATH = ROOT / "design_brain" / "families" / "serviceability_governs" / "runtime.py"

from design_brain.families.serviceability import ServiceabilityFamily  # noqa: E402
from design_brain.families.serviceability_governs import evaluate_serviceability_governs  # noqa: E402
from design_brain.families.serviceability_governs.runtime import (  # noqa: E402
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
FORBIDDEN_RUNTIME_IMPORT_PREFIXES = {
    "inputs_page",
    "streamlit",
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
}
FORBIDDEN_RUNTIME_SOURCE_TERMS = {
    "button_contract",
    "published_item",
    "rendered_html",
    "session_state",
    "st.",
    "apply_routing",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _forbidden_runtime_imports() -> list[str]:
    blocked: list[str] = []
    for imported in _module_imports(RUNTIME_PATH):
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_RUNTIME_IMPORT_PREFIXES):
            blocked.append(imported)
    return sorted(set(blocked))


def _forbidden_runtime_source_hits() -> list[str]:
    source = RUNTIME_PATH.read_text(encoding="utf-8", errors="ignore").lower()
    return sorted(term for term in FORBIDDEN_RUNTIME_SOURCE_TERMS if term.lower() in source)


def _base_state() -> dict[str, Any]:
    return {
        "geometry": {"beam_width_mm": 300.0, "beam_depth_mm": 500.0},
        "reinforcement": {"bottom_bar_count": 3, "bottom_bar_diameter_mm": 20},
        "actions": {"current_serviceability_utilisation": 1.2},
        "failure_flags": {"bending_fail": False, "shear_fail": False},
        "constraints": {},
    }


def _evaluation(
    candidate_input: ServiceabilityCandidateInput,
    candidate_update: ServiceabilityCandidateUpdate,
    *,
    serviceability_utilisation: float,
    serviceability_compliant: bool,
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
        blocker_status={"blocked": False, "reasons": []},
        capacity_summary={"normalised": True},
        failure_flags={
            "serviceability_fail": not serviceability_compliant,
            "bending_fail": False,
            "shear_fail": False,
            "constructability_fail": False,
        },
        engineering_status={"overall": "PASS" if serviceability_compliant else "FAIL"},
    ).with_evaluation_hash()


def _accepting_evaluator(
    candidate_input: ServiceabilityCandidateInput,
    candidate_update: ServiceabilityCandidateUpdate,
) -> ServiceabilityCandidateEvaluation:
    reinforcement = dict((candidate_update.updates or {}).get("reinforcement") or {})
    if reinforcement.get("bottom_bar_count") == 4:
        return _evaluation(candidate_input, candidate_update, serviceability_utilisation=0.96, serviceability_compliant=True)
    return _evaluation(candidate_input, candidate_update, serviceability_utilisation=1.1, serviceability_compliant=False)


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SERVICEABILITY_GOVERNS Cutover Implementation",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(["", "## Runtime Evidence", ""])
    lines.extend(
        [
            f"- runtime_authority: `{snapshot['family_result']['lock_proof'].get('contract_runtime_authority')}`",
            f"- selected_strategy_lane: `{snapshot['runtime_result'].get('selected_strategy_lane')}`",
            f"- ladder_hash: `{snapshot['runtime_result'].get('ladder_hash')}`",
        ]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    package_source = _read("design_brain/families/serviceability_governs/__init__.py")
    family_source = _read("design_brain/families/serviceability.py")
    api_result = evaluate_serviceability_governs(
        {
            "serviceability_inputs": ServiceabilityInputs(base_state=_base_state()),
            "evaluate_candidate": _accepting_evaluator,
        }
    )
    family_result = {
        "family_id": api_result.family_id,
        "status": api_result.status,
        "selected_candidate": api_result.selected_candidate,
        "updates": api_result.updates,
        "blockers": api_result.blockers,
        "evidence": api_result.evidence,
        "publication": api_result.publication,
        "cta_contract": api_result.cta_contract,
        "lock_proof": api_result.lock_proof,
    }
    runtime_result = dict((api_result.evidence or {}).get("runtime_result") or {})
    metadata = ServiceabilityFamily.metadata
    checks = {
        "package_api_delegates_to_runtime": "run_serviceability_governs_ladder_runtime" in package_source
        and "NotImplementedError" not in package_source,
        "public_api_returns_family_result_shape": api_result.family_id == "SERVICEABILITY_GOVERNS"
        and api_result.status == "REPAIRED"
        and bool(api_result.selected_candidate)
        and bool(api_result.updates),
        "runtime_authority_identified": api_result.lock_proof.get("contract_runtime_authority") == "run_serviceability_governs_ladder_runtime"
        and api_result.evidence.get("contract_runtime_authority") == "run_serviceability_governs_ladder_runtime",
        "runtime_result_embedded": runtime_result.get("selected_strategy_lane") == "BOTTOM_REINFORCEMENT_INCREASE"
        and bool(runtime_result.get("ladder_hash")),
        "contract_lane_order_preserved_in_result": tuple(api_result.evidence.get("contract_runtime_lane_order") or ()) == EXPECTED_CONTRACT_ORDER,
        "family_metadata_identifies_runtime_ownership": metadata.candidate_strategy == "contract_runtime_candidate_generation"
        and metadata.ranking_strategy == "contract_runtime_serviceability_ranking"
        and metadata.evidence_strategy == "contract_runtime_exact_stop_exhausted_and_blocker_evidence",
        "runtime_callable": callable(run_serviceability_governs_ladder_runtime),
        "runtime_has_no_page_or_shared_app_imports": not _forbidden_runtime_imports()
        and not _forbidden_runtime_source_hits(),
        "shared_result_surfaces_empty": api_result.publication == {} and api_result.cta_contract == {},
        "no_inputs_page_cutover_required": "inputs_page" not in package_source and "inputs_page" not in family_source,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "serviceability_governs_cutover_implementation.v1",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "family_result": family_result,
        "runtime_result": runtime_result,
        "forbidden_runtime_imports": _forbidden_runtime_imports(),
        "forbidden_runtime_source_hits": _forbidden_runtime_source_hits(),
        "expected_contract_order": list(EXPECTED_CONTRACT_ORDER),
        "scope_limits": {
            "inputs_page_changed": False,
            "shared_app_ownership_moved": False,
            "visible_wording_moved": False,
            "other_locked_families_touched": False,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['status']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
