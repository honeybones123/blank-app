"""Cutover implementation verifier for SHEAR_OVERDESIGN_GOVERNS."""

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

from design_brain.families.shear_cleanup import ShearCleanupFamily, _default_runtime_evaluator  # noqa: E402
from design_brain.families.shear_overdesign_governs import (  # noqa: E402
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)


REQUIRED_SPEC_FIELDS = {
    "label",
    "updates",
    "action_type",
    "contract_step",
    "lane_id",
    "candidate_family_id",
    "ladder_hash",
    "ladder_trace_ref",
    "update_hash",
    "candidate_state_hash",
    "restart_proof",
    "ranking_proof",
    "zero_shear_override_proof",
    "geometry_restriction_proof",
}

FORBIDDEN_RUNTIME_TERMS = {
    "inputs_page",
    "streamlit",
    "st.session_state",
    "session_state",
    "publication",
    "button_contract",
}


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 500.0,
        "Vu": 0.0,
        "design_actions_present": True,
        "s_lig": 100.0,
        "lig_d": 16,
        "lig_legs": 6,
        "shear_utilisation": 0.0,
        "minimum_shear_reinforcement_required": False,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Cutover Implementation",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


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


def main() -> int:
    family = ShearCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(_base_state())
    runtime_result = run_shear_overdesign_governs_runtime(
        base_state=_base_state(),
        evaluate_candidate=_default_runtime_evaluator,
    )
    specs = [dict(spec) for spec in list(ladder.get("specs") or []) if isinstance(spec, dict)]
    first_spec = specs[0] if specs else {}
    runtime_source = (ROOT / "design_brain" / "families" / "shear_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    cleanup_source = (ROOT / "design_brain" / "families" / "shear_cleanup.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    inputs_source = _read_inputs_composition_surface()
    forbidden_runtime_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    missing_spec_fields = sorted(REQUIRED_SPEC_FIELDS - set(first_spec))
    all_updates = [dict(spec.get("updates") or {}) for spec in specs]
    width_keys = {"b", "bw", "beam_width", "beam_width_mm"}
    prohibited_geometry_keys = {"D", "beam_depth", "beam_depth_mm"}
    allowed_update_keys = {"s_lig", "lig_d", "lig_legs"} | width_keys
    checks = {
        "family_method_exists": callable(getattr(family, "contracted_optimisation_ladder_specs", None)),
        "compatibility_alias_exists": callable(getattr(family, "contracted_repair_ladder_specs", None)),
        "contract_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_shear_overdesign_governs_runtime",
        "specs_present": bool(specs),
        "spec_shape_preserved": not missing_spec_fields,
        "specs_include_runtime_evidence": bool(first_spec.get("ladder_hash"))
        and bool(first_spec.get("update_hash"))
        and bool(first_spec.get("candidate_state_hash")),
        "restart_and_ranking_proof_present": any(spec.get("restart_proof") for spec in specs)
        and any(spec.get("ranking_proof") for spec in specs),
        "zero_shear_and_geometry_proof_present": bool(ladder.get("zero_shear_override_proof"))
        and bool(ladder.get("geometry_restriction_proof")),
        "updates_are_contract_allowed": all(
            set(update) <= allowed_update_keys for update in all_updates
        ),
        "width_reduction_updates_present": any(set(update) & width_keys for update in all_updates),
        "no_depth_reduction_updates": not any(set(update) & prohibited_geometry_keys for update in all_updates),
        "package_runtime_export_matches_family_shell": runtime_result.ladder_hash == ladder.get("ladder_hash"),
        "contract_lane_order_preserved": tuple(runtime_result.repair_reason_proof.get("contract_lane_order") or ())
        == shear_overdesign_contract_lane_order(),
        "inputs_page_still_owns_shared_plumbing": "from design_brain.cta_contracts import" in inputs_source
        and "from design_brain.final_publication import" in inputs_source
        and "build_final_design_guide_publication" in inputs_source
        and "handle_inputs_apply_buttons" in inputs_source,
        "runtime_has_no_page_ui_imports": not forbidden_runtime_terms,
        "no_shear_fail_imports": "shear_fail_governs" not in cleanup_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if missing_spec_fields:
        failures.append(f"missing_spec_fields:{missing_spec_fields}")
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    snapshot = {
        "schema": "shear_overdesign_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "contract_lane_order": list(shear_overdesign_contract_lane_order()),
        "spec_count": len(specs),
        "first_spec": first_spec,
        "ladder_hash": ladder.get("ladder_hash"),
        "runtime_result": runtime_result.to_dict(),
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
