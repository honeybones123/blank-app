"""Final lock verifier for SERVICEABILITY_GOVERNS."""

from __future__ import annotations

import ast
import json
import subprocess
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
from design_brain.families.serviceability_governs.contract import (  # noqa: E402
    contract_hash,
    family_identity,
    load_serviceability_governs_contract,
    serviceability_contract_lane_order,
)
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
PROOF_CHAIN = (
    ("contract_check", "tools/verification/families/serviceability_governs_contract_check.py"),
    ("candidate_evaluation_boundary", "tools/verification/serviceability_candidate_evaluation_boundary_snapshot.py"),
    ("lane_snapshot", "tools/verification/families/serviceability_governs_lane_snapshot.py"),
    ("ladder_runtime", "tools/verification/families/serviceability_governs_ladder_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/serviceability_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/serviceability_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/serviceability_governs_cutover_implementation.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
)
FORBIDDEN_RUNTIME_IMPORT_PREFIXES = {
    "inputs_page",
    "streamlit",
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
}
FORBIDDEN_RUNTIME_SOURCE_TERMS = {
    "st.",
    "session_state",
    "button_contract",
    "published_item",
    "rendered_html",
    "apply_routing",
    "one_click",
    "visible_wording",
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


def _run_tool(name: str, script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    stdout = str(completed.stdout or "")
    return {
        "name": name,
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": stdout[-1200:],
        "stderr_tail": str(completed.stderr or "")[-1200:],
    }


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
        capacity_summary={"verifier": "serviceability_governs_lock"},
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
    return _evaluation(candidate_input, candidate_update, serviceability_utilisation=1.11, serviceability_compliant=False)


def _runtime_boundary_snapshot() -> dict[str, Any]:
    source = RUNTIME_PATH.read_text(encoding="utf-8", errors="ignore")
    lower = source.lower()
    imports = _module_imports(RUNTIME_PATH)
    forbidden_imports = sorted(
        imported
        for imported in imports
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_RUNTIME_IMPORT_PREFIXES)
    )
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_SOURCE_TERMS if term.lower() in lower)
    return {
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_terms": forbidden_terms,
    }


def _inputs_page_shared_ownership() -> dict[str, bool]:
    retired = (
        "inputs_page_route_coordinators.py",
        "inputs_page_app_contract_bridge.py",
    )
    if any((ROOT / path).exists() for path in retired):
        raise AssertionError("retired Inputs composition bridges must remain absent")
    source = "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_application/candidate_full_evaluation.py",
            "inputs_application/page_runtime/design_guide.py",
            "inputs_application/page_runtime/design_guide_runtime_support.py",
            "inputs_page_modules/apply_routing.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
            "inputs_page_modules/guidance_compute.py",
        )
    )
    lower = source.lower()
    return {
        "candidate_evaluation_loop": "_evaluate_auto_design_candidate(" in source
        and (
            "def evaluate_candidate_full" in source
            or "evaluate_candidate_full_for_app_bridge" in source
        ),
        "publication": "record_design_guide_publication_snapshot" in source
        or "_FINAL_PUBLICATION_CTA_AUTHORITY" in source,
        "apply_routing": "build_design_guide_apply_button_contract" in source
        or "handle_inputs_apply_buttons" in source
        or "apply_resolved_candidate_payload" in source,
        "one_click": "one_click" in lower,
        "ui_session_debug": "st.session_state" in source and "debug" in lower,
    }


def _api_snapshot() -> dict[str, Any]:
    result = evaluate_serviceability_governs(
        {
            "serviceability_inputs": ServiceabilityInputs(base_state=_base_state()),
            "evaluate_candidate": _accepting_evaluator,
        }
    )
    return {
        "family_id": result.family_id,
        "status": result.status,
        "selected_candidate": result.selected_candidate,
        "updates": result.updates,
        "publication": result.publication,
        "cta_contract": result.cta_contract,
        "evidence_authority": (result.evidence or {}).get("contract_runtime_authority"),
        "lock_proof": dict(result.lock_proof or {}),
        "runtime_result": dict((result.evidence or {}).get("runtime_result") or {}),
        "contract_runtime_lane_order": tuple((result.evidence or {}).get("contract_runtime_lane_order") or ()),
    }


def _runtime_snapshot() -> dict[str, Any]:
    first = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state()),
        evaluate_candidate=_accepting_evaluator,
    )
    second = run_serviceability_governs_ladder_runtime(
        serviceability_inputs=ServiceabilityInputs(base_state=_base_state()),
        evaluate_candidate=_accepting_evaluator,
    )
    return {
        "status": first.status,
        "selected_strategy_lane": first.selected_strategy_lane,
        "ladder_hash": first.ladder_hash,
        "repeat_ladder_hash": second.ladder_hash,
        "ladder_hash_stable": first.ladder_hash == second.ladder_hash,
        "candidate_repairs_count": len(first.candidate_repairs),
        "has_evidence": bool(first.evidence),
        "ownership_proof": dict(first.ownership_proof),
    }


def _strategy_gateway_snapshot() -> dict[str, Any]:
    result = ServiceabilityFamily().contracted_serviceability_ladder_result(_base_state())
    return {
        "runtime_authority": result.get("runtime_authority"),
        "contract_runtime_driven": result.get("contract_runtime_driven"),
        "has_ladder_hash": bool(result.get("ladder_hash")),
        "status": result.get("status"),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SERVICEABILITY_GOVERNS Lock Verifier",
        "",
        f"Status: `{snapshot['status']}`",
        f"Lock status: `{snapshot['lock_status']}`",
        "",
        "## Proof Chain",
        "",
    ]
    lines.extend(f"- `{row['name']}`: `{row['passed']}`" for row in snapshot["proof_chain"])
    lines.extend(["", "## Direct Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = load_serviceability_governs_contract()
    identity = family_identity()
    proof_chain = [_run_tool(name, script) for name, script in PROOF_CHAIN]
    runtime = _runtime_snapshot()
    api = _api_snapshot()
    strategy_gateway = _strategy_gateway_snapshot()
    boundary = _runtime_boundary_snapshot()
    shared = _inputs_page_shared_ownership()
    contract_order = serviceability_contract_lane_order()
    checks = {
        "proof_chain_pass": all(row["passed"] for row in proof_chain),
        "contract_loads": isinstance(contract, dict) and bool(contract),
        "contract_family_id": identity.get("family_id") == "SERVICEABILITY_GOVERNS",
        "contract_hash_present": bool(contract_hash()),
        "contract_lane_order_exact": contract_order == EXPECTED_CONTRACT_ORDER,
        "runtime_reads_contract_lane_order": api["contract_runtime_lane_order"] == EXPECTED_CONTRACT_ORDER,
        "runtime_hash_stable": runtime["ladder_hash_stable"],
        "runtime_selected_repair_proven": runtime["status"] == "REPAIRED"
        and runtime["selected_strategy_lane"] == "BOTTOM_REINFORCEMENT_INCREASE",
        "api_identifies_runtime_authority": api["evidence_authority"] == "run_serviceability_governs_ladder_runtime"
        and api["lock_proof"].get("contract_runtime_authority") == "run_serviceability_governs_ladder_runtime",
        "api_does_not_publish_or_generate_action_contract": api["publication"] == {}
        and api["cta_contract"] == {},
        "strategy_gateway_reaches_runtime": strategy_gateway["contract_runtime_driven"] is True
        and strategy_gateway["runtime_authority"] == "run_serviceability_governs_ladder_runtime"
        and strategy_gateway["has_ladder_hash"] is True,
        "inputs_page_still_owns_shared_surfaces": all(shared.values()),
        "retired_inputs_bridges_absent": not (ROOT / "inputs_page_route_coordinators.py").exists()
        and not (ROOT / "inputs_page_app_contract_bridge.py").exists(),
        "runtime_has_no_forbidden_imports_or_ownership_terms": not boundary["forbidden_imports"]
        and not boundary["forbidden_source_terms"],
        "ownership_proof_keeps_shared_systems_out": runtime["ownership_proof"].get("shared_system_ownership_not_entered") is True,
    }
    failures = [key for key, passed in checks.items() if not passed]
    failed_chain = [row["name"] for row in proof_chain if not row["passed"]]
    if failed_chain:
        failures.append(f"failed_proof_chain:{failed_chain}")
    snapshot = {
        "schema": "serviceability_governs_lock_verifier.v1",
        "status": "PASS" if not failures else "FAIL",
        "lock_status": "SERVICEABILITY_GOVERNS lock complete" if not failures else "SERVICEABILITY_GOVERNS lock incomplete",
        "checks": checks,
        "failures": failures,
        "contract_family_id": identity.get("family_id"),
        "contract_lane_order": list(contract_order),
        "proof_chain": proof_chain,
        "runtime": runtime,
        "api": api,
        "strategy_gateway": strategy_gateway,
        "runtime_boundary": boundary,
        "inputs_page_shared_ownership": shared,
        "scope_limits": {
            "moves_family_selection": False,
            "moves_publication": False,
            "moves_cta": False,
            "moves_apply_routing": False,
            "moves_one_click": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SERVICEABILITY_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SERVICEABILITY_GOVERNS lock verifier PASS")
    print("SERVICEABILITY_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
