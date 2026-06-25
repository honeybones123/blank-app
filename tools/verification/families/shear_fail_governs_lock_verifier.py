"""Final lock verifier for SHEAR_FAIL_GOVERNS.

This composes the post-cutover SHEAR proof chain. The stale pre-cutover locked
regression is deliberately not an authority for this verifier.
"""

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

from design_brain.families.shear_fail import ShearFailFamily  # noqa: E402
from design_brain.families.shear_fail_governs import evaluate_shear_fail_governs  # noqa: E402
from design_brain.families.shear_fail_governs.contract import (  # noqa: E402
    family_identity,
    internal_strategy_lanes,
    load_shear_fail_governs_contract,
)
from design_brain.families.shear_fail_governs.runtime import (  # noqa: E402
    run_shear_fail_governs_ladder_runtime,
    shear_fail_governs_contract_lane_order,
)
from design_brain.shear_candidate_evaluation import (  # noqa: E402
    ShearCandidateEvaluation,
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

PROOF_CHAIN = (
    ("contract_check", "tools/verification/families/shear_fail_governs_contract_check.py"),
    ("candidate_evaluation_boundary", "tools/verification/shear_candidate_evaluation_boundary_snapshot.py"),
    ("spacing_lane", "tools/verification/families/shear_fail_governs_spacing_lane_snapshot.py"),
    ("bar_size_lane", "tools/verification/families/shear_fail_governs_bar_size_lane_snapshot.py"),
    ("depth_reset_lane", "tools/verification/families/shear_fail_governs_depth_reset_lane_snapshot.py"),
    ("width_reset_lane", "tools/verification/families/shear_fail_governs_width_reset_lane_snapshot.py"),
    ("leg_count_lane", "tools/verification/families/shear_fail_governs_leg_count_lane_snapshot.py"),
    ("terminal_lane", "tools/verification/families/shear_fail_governs_terminal_lane_snapshot.py"),
    ("ladder_runtime", "tools/verification/families/shear_fail_governs_ladder_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/shear_fail_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/shear_fail_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/shear_fail_governs_cutover_implementation.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
)

REQUIRED_SPEC_FIELDS = {
    "lane_id",
    "ladder_hash",
    "update_hash",
    "candidate_state_hash",
    "restart_proof",
    "ranking_proof",
}

FORBIDDEN_RUNTIME_IMPORT_PREFIXES = {
    "inputs_page",
    "streamlit",
    "design_brain.publication",
    "design_brain.output_formatting",
    "design_brain.cta_contracts",
    "design_brain.families.bending",
    "design_brain.families.bending_fail",
    "design_brain.families.bending_fail_governs",
}

FORBIDDEN_RUNTIME_SOURCE_TERMS = {
    "st.",
    "session_state",
    "button_contract",
    "published_item",
    "rendered_html",
    "apply_resolved_candidate",
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
        timeout=180,
    )
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    first_status_line = next(
        (
            line.strip()
            for line in stdout.splitlines()
            if line.strip().startswith(("PASS:", "FAIL:", "SHEAR_FAIL_GOVERNS"))
        ),
        "",
    )
    return {
        "name": name,
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "status_line": first_status_line,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def _runtime_fixture_state() -> dict[str, Any]:
    return {
        "geometry": {
            "beam_width_mm": 400.0,
            "beam_depth_mm": 600.0,
            "geometry_locked": False,
        },
        "reinforcement": {
            "ligature_spacing_mm": 300.0,
            "ligature_diameter_mm": 10,
            "ligature_leg_count": 2,
        },
        "constraints": {
            "geometry_locked": False,
            "minimum_spacing_mm": 100.0,
        },
    }


def _family_fixture_state() -> dict[str, Any]:
    return {
        "b": 400.0,
        "D": 600.0,
        "s_lig": 300.0,
        "lig_d": 10,
        "lig_legs": 2,
    }


def _rejecting_evaluator(candidate_input: Any, candidate_update: Any) -> ShearCandidateEvaluation:
    return ShearCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        shear_utilisation=1.2,
        previous_shear_utilisation=1.2,
        utilisation_improved=False,
        code_compliance_status={"overall": "FAIL"},
        constructability_status={"overall": "CHECKED"},
        spacing_status={"status": "CHECKED"},
        bar_size_status={"status": "CHECKED"},
        leg_count_status={"status": "CHECKED"},
        geometry_status={"status": "CHECKED"},
        capacity_summary={"verifier": "shear_fail_governs_lock_rejecting_evaluator"},
        failure_flags={"shear_fail": True},
        engineering_status={"overall": "FAIL", "target_band_status": "FAIL"},
    ).with_evaluation_hash()


def _runtime_snapshot() -> dict[str, Any]:
    first = run_shear_fail_governs_ladder_runtime(
        base_state=_runtime_fixture_state(),
        evaluate_candidate=_rejecting_evaluator,
    )
    second = run_shear_fail_governs_ladder_runtime(
        base_state=_runtime_fixture_state(),
        evaluate_candidate=_rejecting_evaluator,
    )
    return {
        "lane_order": list(shear_fail_governs_contract_lane_order()),
        "ladder_hash": first.ladder_hash,
        "repeat_ladder_hash": second.ladder_hash,
        "ladder_hash_stable": bool(first.ladder_hash) and first.ladder_hash == second.ladder_hash,
        "candidate_repairs_count": len(first.candidate_repairs),
        "required_fields_present": all(
            hasattr(first, field)
            for field in (
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
            )
        ),
    }


def _family_specs_snapshot() -> dict[str, Any]:
    family = ShearFailFamily()
    first = family.contracted_repair_ladder_specs(_family_fixture_state(), geometry_locked=False)
    second = family.contracted_repair_ladder_specs(_family_fixture_state(), geometry_locked=False)
    specs = [dict(spec) for spec in list(first.get("specs") or []) if isinstance(spec, dict)]
    missing_fields = {
        str(spec.get("lane_id") or spec.get("label") or f"spec_{index}"): sorted(REQUIRED_SPEC_FIELDS - set(spec))
        for index, spec in enumerate(specs, start=1)
        if REQUIRED_SPEC_FIELDS - set(spec)
    }
    restart_proof_count = sum(1 for spec in specs if isinstance(spec.get("restart_proof"), dict))
    ranking_proof_count = sum(1 for spec in specs if spec.get("ranking_proof") is not None)
    return {
        "runtime_authority": first.get("runtime_authority"),
        "ladder_hash": first.get("ladder_hash"),
        "repeat_ladder_hash": second.get("ladder_hash"),
        "ladder_hash_stable": bool(first.get("ladder_hash")) and first.get("ladder_hash") == second.get("ladder_hash"),
        "spec_count": len(specs),
        "missing_required_spec_fields": missing_fields,
        "restart_proof_count": restart_proof_count,
        "ranking_proof_count": ranking_proof_count,
        "has_ladder_trace": bool(first.get("ladder_trace")),
        "has_accepted_or_rejected_evidence": bool(first.get("accepted_lane_evidence") or first.get("rejected_lane_evidence")),
    }


def _package_authority_snapshot() -> dict[str, Any]:
    result = evaluate_shear_fail_governs({"summary": {}, "evidence": {}, "debug": {}})
    evidence = dict(getattr(result, "evidence", {}) or {})
    lock_proof = dict(getattr(result, "lock_proof", {}) or {})
    return {
        "evidence_authority": evidence.get("contract_runtime_authority"),
        "lock_proof_authority": lock_proof.get("contract_runtime_authority"),
        "product_routing_enabled": lock_proof.get("product_routing_enabled"),
        "contract_runtime_lane_order": list(lock_proof.get("contract_runtime_lane_order") or ()),
    }


def _inputs_page_ownership_snapshot() -> dict[str, bool]:
    source = _read("inputs_page.py")
    lower = source.lower()
    return {
        "evaluate_loop": "def _evaluate(" in source,
        "candidate_evaluation_calls": "_evaluate_auto_design_candidate(" in source or "_evaluate_candidate_fast(" in source,
        "cta_rendering": "button_contract" in source or "cta" in lower,
        "publication": "publication" in lower or "published_item" in lower,
        "apply_routing": "apply_resolved_candidate" in source or "apply_payload" in source,
        "one_click": "one_click" in lower,
        "visible_wording": "_design_guide_dashboard_reasons" in source or "why_text" in source,
        "ui_session_debug": "st.session_state" in source and "debug" in lower,
    }


def _runtime_boundary_snapshot() -> dict[str, Any]:
    runtime_path = ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py"
    source = runtime_path.read_text(encoding="utf-8", errors="ignore")
    lower = source.lower()
    imports = _module_imports(runtime_path)
    forbidden_imports = sorted(
        imported
        for imported in imports
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_RUNTIME_IMPORT_PREFIXES)
    )
    forbidden_source_terms = sorted(term for term in FORBIDDEN_RUNTIME_SOURCE_TERMS if term.lower() in lower)
    return {
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_terms": forbidden_source_terms,
    }


def _no_bending_dependency_snapshot() -> dict[str, Any]:
    runtime_imports = _module_imports(ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py")
    chain_paths = [script for _, script in PROOF_CHAIN]
    return {
        "proof_chain_paths_with_bending": [path for path in chain_paths if "bending" in path.lower()],
        "runtime_imports_with_bending": [item for item in runtime_imports if "bending" in item.lower()],
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_lock_verifier_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SHEAR_FAIL_GOVERNS Lock Verifier",
        "",
        f"Status: `{snapshot['status']}`",
        f"Lock status: `{snapshot['lock_status']}`",
        "",
        "## Proof Chain",
        "",
    ]
    lines.extend(
        f"- `{row['name']}`: `{'PASS' if row['passed'] else 'FAIL'}`"
        for row in snapshot["proof_chain"]
    )
    lines.extend(["", "## Direct Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(
        [
            "",
            "## Contract Order",
            "",
            "```text",
            "\n".join(snapshot["contract_lane_order"]),
            "```",
            "",
            "## Failures",
            "",
        ]
    )
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    contract = load_shear_fail_governs_contract()
    identity = family_identity()
    contract_order = tuple(str(lane.get("lane_id") or "") for lane in internal_strategy_lanes())
    runtime_order = tuple(shear_fail_governs_contract_lane_order())
    proof_chain = [_run_tool(name, script) for name, script in PROOF_CHAIN]
    runtime = _runtime_snapshot()
    specs = _family_specs_snapshot()
    package = _package_authority_snapshot()
    inputs_page = _inputs_page_ownership_snapshot()
    runtime_boundary = _runtime_boundary_snapshot()
    bending_dependency = _no_bending_dependency_snapshot()

    checks = {
        "contract_loads": isinstance(contract, dict) and bool(contract),
        "contract_family_id": identity.get("family_id") == "SHEAR_FAIL_GOVERNS",
        "contract_lane_order_exact": contract_order == EXPECTED_CONTRACT_ORDER,
        "runtime_reads_contract_lane_order": runtime_order == contract_order == EXPECTED_CONTRACT_ORDER,
        "proof_chain_pass": all(row["passed"] for row in proof_chain),
        "runtime_hash_stable": runtime["ladder_hash_stable"],
        "runtime_required_fields_present": runtime["required_fields_present"],
        "contracted_repair_ladder_specs_runtime_driven": specs["runtime_authority"] == "run_shear_fail_governs_ladder_runtime",
        "family_specs_hash_stable": specs["ladder_hash_stable"],
        "returned_specs_include_required_runtime_evidence": specs["spec_count"] > 0
        and not specs["missing_required_spec_fields"]
        and specs["restart_proof_count"] > 0
        and specs["ranking_proof_count"] > 0
        and specs["has_ladder_trace"]
        and specs["has_accepted_or_rejected_evidence"],
        "evaluate_api_identifies_runtime_authority": package["evidence_authority"] == "run_shear_fail_governs_ladder_runtime"
        and package["lock_proof_authority"] == "run_shear_fail_governs_ladder_runtime",
        "inputs_page_still_owns_shared_plumbing": all(inputs_page.values()),
        "runtime_has_no_forbidden_imports_or_ownership_terms": not runtime_boundary["forbidden_imports"]
        and not runtime_boundary["forbidden_source_terms"],
        "no_bending_files_required": not bending_dependency["proof_chain_paths_with_bending"]
        and not bending_dependency["runtime_imports_with_bending"],
    }
    failures = [key for key, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "shear_fail_governs_lock_verifier.v1",
        "status": status,
        "lock_status": "SHEAR_FAIL_GOVERNS lock complete" if status == "PASS" else "SHEAR_FAIL_GOVERNS lock incomplete",
        "checks": checks,
        "failures": failures,
        "contract_family_id": identity.get("family_id"),
        "contract_lane_order": list(contract_order),
        "runtime_lane_order": list(runtime_order),
        "proof_chain": proof_chain,
        "runtime": runtime,
        "family_specs": specs,
        "package_authority": package,
        "inputs_page_ownership": inputs_page,
        "runtime_boundary": runtime_boundary,
        "bending_dependency": bending_dependency,
        "scope_limits": {
            "uses_stale_pre_cutover_locked_regression_as_authority": False,
            "moves_cta_rendering": False,
            "moves_publication": False,
            "moves_apply_routing": False,
            "moves_one_click": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
            "requires_bending_files": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if status != "PASS":
        print("SHEAR_FAIL_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("SHEAR_FAIL_GOVERNS lock verifier PASS")
    print("SHEAR_FAIL_GOVERNS lock complete")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
