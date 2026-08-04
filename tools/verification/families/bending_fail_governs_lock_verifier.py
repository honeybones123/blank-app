"""Final lock verifier for BENDING_FAIL_GOVERNS.

This composes the contract, candidate-evaluation boundary, ladder runtime,
replacement audit, cutover plan, and cutover implementation proofs into one
lock gate.
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

from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs import (  # noqa: E402
    run_bending_fail_governs_ladder_runtime,
)
from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    family_identity,
    load_bending_fail_governs_contract,
)
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    bending_fail_governs_contract_lane_order,
)


EXPECTED_CONTRACT_ORDER = (
    "GEOMETRY_SANITY",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "MULTI_LAYER_REO",
    "DEPTH_INCREASE",
    "WIDTH_INCREASE",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

PROOF_CHAIN = (
    ("candidate_evaluation_boundary", "tools/verification/candidate_evaluation_boundary_snapshot.py"),
    ("ladder_runtime", "tools/verification/families/bending_fail_governs_ladder_runtime_snapshot.py"),
    ("replacement_audit", "tools/verification/families/bending_fail_governs_replacement_audit.py"),
    ("cutover_plan", "tools/verification/families/bending_fail_governs_cutover_plan.py"),
    ("cutover_implementation", "tools/verification/families/bending_fail_governs_cutover_implementation.py"),
    ("live_wiring", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
)

REQUIRED_SPEC_FIELDS = {
    "contract_runtime_lane_id",
    "ladder_hash",
    "update_hash",
    "candidate_state_hash",
    "ladder_trace_evidence",
}

FORBIDDEN_RUNTIME_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
}

FORBIDDEN_RUNTIME_SOURCE_TERMS = {
    "st.session_state",
    "session_state",
    "button_label",
    "button_contract",
    "publication",
    "published_item",
    "apply_routing",
    "rendered_html",
    "visible_wording",
}

SHEAR_IMPLEMENTATION_PATHS = (
    "design_brain/families/shear_fail.py",
    "design_brain/families/shear_fail_governs",
    "design_brain/families/shear_overdesign_governs",
    "design_brain/families/shear_fail_bending_overdesign_governs",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _read_inputs_composition_surface() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_application/page_runtime/common.py",
            "inputs_application/page_runtime/design_guide_runtime_support.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
            "inputs_page_modules/design_guide/primary_button_queue.py",
            "inputs_page_modules/guidance_compute.py",
        )
        if (ROOT / path).exists()
    )


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
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
        timeout=120,
    )
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    result_text = f"{stdout}\n{stderr}".lower()
    return {
        "name": name,
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0 and "pass" in result_text and " fail" not in result_text,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def _fixture_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "cover_side": 40.0,
        "lig_d": 0,
    }


def _family_ladder_snapshot() -> dict[str, Any]:
    family = BendingFailFamily()
    first = family.contracted_repair_ladder_specs(_fixture_state(), geometry_locked=False)
    second = family.contracted_repair_ladder_specs(_fixture_state(), geometry_locked=False)
    specs = [dict(spec) for spec in list(first.get("specs") or []) if isinstance(spec, dict)]
    missing_by_spec = {
        str(spec.get("contract_runtime_lane_id") or spec.get("label") or f"spec_{index}"): sorted(
            REQUIRED_SPEC_FIELDS - set(spec)
        )
        for index, spec in enumerate(specs, start=1)
    }
    missing_evidence = [
        lane
        for lane, missing in missing_by_spec.items()
        if missing
        or not isinstance(
            next(
                (
                    spec.get("ladder_trace_evidence")
                    for spec in specs
                    if str(spec.get("contract_runtime_lane_id") or spec.get("label") or "") == lane
                ),
                {},
            ),
            dict,
        )
    ]
    return {
        "contract_runtime_driven": bool(first.get("contract_runtime_driven")),
        "contract_runtime_authority": first.get("contract_runtime_authority"),
        "legacy_ladder_order_authority_field_absent": "legacy_ladder_order_authority" not in first,
        "contract_lane_order": list(first.get("contract_lane_order") or []),
        "ladder_hash": first.get("ladder_hash"),
        "repeat_ladder_hash": second.get("ladder_hash"),
        "ladder_hash_stable": first.get("ladder_hash") == second.get("ladder_hash"),
        "spec_count": len(specs),
        "spec_lane_order": [spec.get("contract_runtime_lane_id") for spec in specs],
        "missing_required_spec_evidence": missing_evidence,
        "accepted_trace_count": len(list(first.get("accepted_lane_evidence") or [])),
        "rejected_trace_count": len(list(first.get("rejected_lane_evidence") or [])),
        "has_terminal_or_no_candidate_proof": bool(first.get("blocked_reason") or first.get("repair_reason_proof")),
    }


def _package_authority_snapshot() -> dict[str, Any]:
    package_source = _read("design_brain/families/bending_fail_governs/__init__.py")
    runtime_source = _read("design_brain/families/bending_fail_governs/runtime.py")
    return {
        "runtime_exported": "run_bending_fail_governs_ladder_runtime" in package_source,
        "runtime_callable": callable(run_bending_fail_governs_ladder_runtime),
        "runtime_defined": "def run_bending_fail_governs_ladder_runtime" in runtime_source,
        "compatibility_api_absent": "evaluate_" + "bending_fail_governs" not in package_source,
        "contract_lane_order": list(bending_fail_governs_contract_lane_order()),
    }


def _inputs_page_ownership_snapshot() -> dict[str, bool]:
    source = _read_inputs_composition_surface()
    lower = source.lower()
    return {
        "evaluate_loop": (
            "def _evaluate(" in source
            or "evaluate_candidate_full_for_app_bridge(" in source
            or "evaluate_candidate_full(" in source
        ),
        "candidate_evaluator": "_evaluate_auto_design_candidate(" in source,
        "cta_rendering_or_contract": "button_contract" in source or "cta_" in lower,
        "publication": "publication" in lower or "FinalDesignGuidePublication" in source,
        "apply_routing": "apply_resolved_candidate" in source,
        "one_click": "one_click" in source,
        "visible_wording": "visible_wording" in source or "why_text" in source,
        "ui_session_debug": "st.session_state" in source and "debug" in lower,
    }


def _runtime_boundary_snapshot() -> dict[str, Any]:
    source = _read("design_brain/families/bending_fail_governs/runtime.py")
    imports = _module_imports(source)
    forbidden_imports = [
        item for item in imports if item.split(".", 1)[0] in FORBIDDEN_RUNTIME_IMPORT_ROOTS
    ]
    source_lower = source.lower()
    forbidden_terms = sorted(term for term in FORBIDDEN_RUNTIME_SOURCE_TERMS if term.lower() in source_lower)
    return {
        "imports": imports,
        "forbidden_imports": forbidden_imports,
        "forbidden_source_terms": forbidden_terms,
    }


def _shear_status() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--", *SHEAR_IMPLEMENTATION_PATHS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    changed = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
    return {
        "changed_tracked_files": changed,
        "diff_returncode": completed.returncode,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_lock_verifier_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Lock Verifier",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Proof Chain",
                "",
                *[
                    f"- `{row['name']}`: `{'PASS' if row['passed'] else 'FAIL'}`"
                    for row in snapshot["proof_chain"]
                ],
                "",
                "## Checks",
                "",
                *[f"- {name}: `{value}`" for name, value in snapshot["checks"].items()],
                "",
                "## Contract Order",
                "",
                "```text",
                " -> ".join(snapshot["contract_lane_order"]),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    contract = load_bending_fail_governs_contract()
    identity = family_identity()
    contract_order = bending_fail_governs_contract_lane_order()
    proof_chain = [_run_tool(name, script) for name, script in PROOF_CHAIN]
    ladder = _family_ladder_snapshot()
    package = _package_authority_snapshot()
    inputs_page = _inputs_page_ownership_snapshot()
    runtime_boundary = _runtime_boundary_snapshot()
    shear = _shear_status()

    checks = {
        "contract_loads": isinstance(contract, dict) and bool(contract),
        "contract_family_id": identity.get("family_id") == "BENDING_FAIL_GOVERNS",
        "contract_lane_order_exact": contract_order == EXPECTED_CONTRACT_ORDER,
        "candidate_evaluation_boundary_pass": next(
            row["passed"] for row in proof_chain if row["name"] == "candidate_evaluation_boundary"
        ),
        "ladder_runtime_pass": next(row["passed"] for row in proof_chain if row["name"] == "ladder_runtime"),
        "replacement_audit_pass": next(row["passed"] for row in proof_chain if row["name"] == "replacement_audit"),
        "cutover_plan_pass": next(row["passed"] for row in proof_chain if row["name"] == "cutover_plan"),
        "cutover_implementation_pass": next(
            row["passed"] for row in proof_chain if row["name"] == "cutover_implementation"
        ),
        "contracted_ladder_runtime_driven": ladder["contract_runtime_driven"]
        and ladder["contract_runtime_authority"] == "run_bending_fail_governs_ladder_runtime"
        and ladder["legacy_ladder_order_authority_field_absent"],
        "returned_specs_include_runtime_evidence": ladder["spec_count"] > 0
        and not ladder["missing_required_spec_evidence"]
        and ladder["accepted_trace_count"] > 0
        and ladder["rejected_trace_count"] > 0,
        "package_exports_runtime_authority_without_compatibility_api": package["runtime_exported"]
        and package["runtime_callable"]
        and package["runtime_defined"]
        and package["compatibility_api_absent"]
        and package["contract_lane_order"] == list(EXPECTED_CONTRACT_ORDER),
        "inputs_page_still_owns_shared_plumbing": all(inputs_page.values()),
        "runtime_has_no_page_ui_imports": not runtime_boundary["forbidden_imports"]
        and not runtime_boundary["forbidden_source_terms"],
        "ladder_hash_stable": bool(ladder["ladder_hash"]) and ladder["ladder_hash_stable"],
        "shear_files_not_required_or_touched": not shear["changed_tracked_files"],
    }
    snapshot = {
        "schema": "bending_fail_governs_lock_verifier.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "contract_family_id": identity.get("family_id"),
        "contract_lane_order": list(contract_order),
        "proof_chain": proof_chain,
        "family_ladder": ladder,
        "package_authority": package,
        "inputs_page_ownership": inputs_page,
        "runtime_boundary": runtime_boundary,
        "shear_status": shear,
        "scope_limits": {
            "moves_cta_rendering": False,
            "moves_publication": False,
            "moves_apply_routing": False,
            "moves_one_click": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
            "begins_shear_fail_governs": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)

    if snapshot["result"] != "PASS":
        print("BENDING_FAIL_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1

    print("BENDING_FAIL_GOVERNS lock verifier PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
