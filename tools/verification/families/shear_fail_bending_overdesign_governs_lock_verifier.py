from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

CHECKS = (
    ("contract check", "tools/verification/families/shear_fail_bending_overdesign_governs_contract_check.py"),
    ("candidate merge boundary", "tools/verification/shear_fail_bending_overdesign_candidate_merge_boundary_snapshot.py"),
    ("source priority", "tools/verification/families/shear_fail_bending_overdesign_governs_source_priority_snapshot.py"),
    ("runtime snapshot", "tools/verification/families/shear_fail_bending_overdesign_governs_runtime_snapshot.py"),
    ("replacement audit", "tools/verification/families/shear_fail_bending_overdesign_governs_replacement_audit.py"),
    ("cutover plan", "tools/verification/families/shear_fail_bending_overdesign_governs_cutover_plan.py"),
    ("cutover implementation", "tools/verification/families/shear_fail_bending_overdesign_governs_cutover_implementation.py"),
    ("live wiring snapshot", "tools/verification/families/locked_family_live_wiring_snapshot.py"),
)


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "pass": proc.returncode == 0,
    }


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _read_inputs_composition_surface() -> str:
    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_page_route_coordinators.py",
            "inputs_page_app_contract_bridge.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
        )
    )


def _static_checks() -> dict[str, bool]:
    runtime = _read("design_brain/families/shear_fail_bending_overdesign_governs/runtime.py")
    registry = _read("design_brain/families/registry.py")
    chooser = _read("design_brain/family_chooser.py")
    classifier = _read("design_brain/family_classification_runtime.py")
    inputs_surface = _read_inputs_composition_surface()
    evaluator = _read("design_brain/candidate_evaluation.py")
    controller = _read("design_brain/design_guide_controller.py")
    return {
        "runtime_authority_present": "run_shear_fail_bending_overdesign_runtime" in runtime,
        "runtime_has_no_page_import": "inputs_page" not in runtime and "streamlit" not in runtime,
        "runtime_has_no_shared_ui_terms": all(
            term not in runtime.lower()
            for term in ("button_contract", "publication", "apply_routing", "one_click", "st.session_state")
        ),
        "registry_contains_family": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in registry,
        "registry_contains_legacy_alias": "SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS" in registry,
        "chooser_contains_family": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in chooser,
        "classification_runtime_contains_family": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in classifier,
        "candidate_evaluation_keeps_evaluator_boundary": "def evaluate_design_candidate_with_updates(" in evaluator,
        "inputs_composition_keeps_auto_candidate_runner": "_evaluate_auto_design_candidate(" in inputs_surface,
        "controller_keeps_final_publication_bridge": "build_final_design_guide_publication" in controller,
        "inputs_composition_keeps_shared_surfaces": "from design_brain.cta_contracts import" in inputs_surface
        and "from design_brain.final_publication import" in inputs_surface
        and "build_final_design_guide_publication" in inputs_surface
        and "handle_inputs_apply_buttons" in inputs_surface,
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_lock_verifier_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_lock_verifier_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS Lock Verifier",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Gates",
                "",
                *[f"- `{row['name']}`: `{'PASS' if row['pass'] else 'FAIL'}`" for row in snapshot["checks"]],
                "",
                "## Static Ownership",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["static_checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    rows = [{"name": name, **_run(script)} for name, script in CHECKS]
    static_checks = _static_checks()
    failures = [f"gate_failed:{row['name']}" for row in rows if not row["pass"]]
    failures.extend(f"static_check_failed:{key}" for key, passed in static_checks.items() if not passed)
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_lock_verifier.v1",
        "result": "PASS" if not failures else "FAIL",
        "family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "checks": rows,
        "static_checks": static_checks,
        "scope": {
            "runtime_authority": "run_shear_fail_bending_overdesign_runtime",
            "mandatory_source": "SHEAR_FAIL_GOVERNS",
            "opportunistic_source": "BENDING_OVERDESIGN_GOVERNS",
            "shared_surfaces_moved": False,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS lock verifier FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS lock verifier PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
