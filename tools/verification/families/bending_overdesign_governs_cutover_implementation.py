"""Cutover implementation verifier for BENDING_OVERDESIGN_GOVERNS."""

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

from design_brain.families.bending_cleanup import BendingCleanupFamily  # noqa: E402
from design_brain.families.bending_overdesign_governs import (  # noqa: E402
    bending_overdesign_contract_lane_order,
    evaluate_bending_overdesign_governs,
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
    "minimum_reinforcement_proof",
    "geometry_compliance_proof",
}

ALLOWED_UPDATE_KEYS = {
    "bot1_count",
    "db_bot_1",
    "bot2_count",
    "db_bot_2",
    "bot_row_count",
    "bot_row_1_bars",
    "bot_row_1_dia",
    "bot_row_2_bars",
    "bot_row_2_dia",
    "b",
    "bw",
    "D",
    "beam_width",
    "beam_depth",
    "beam_width_mm",
    "beam_depth_mm",
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
        "Mstar": 220.0,
        "phiMu": 330.0,
        "bending_utilisation": 0.67,
        "As": 2260.0,
        "As_min": 950.0,
        "bot1_count": 5,
        "db_bot_1": 24,
        "bot_row_count": 1,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_overdesign_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_overdesign_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_OVERDESIGN_GOVERNS Cutover Implementation",
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


def main() -> int:
    family = BendingCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(_base_state())
    api_result = evaluate_bending_overdesign_governs({"state": _base_state()})
    specs = [dict(spec) for spec in list(ladder.get("specs") or []) if isinstance(spec, dict)]
    first_spec = specs[0] if specs else {}
    runtime_source = (ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    cleanup_source = (ROOT / "design_brain" / "families" / "bending_cleanup.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    forbidden_runtime_terms = sorted(term for term in FORBIDDEN_RUNTIME_TERMS if term in runtime_source)
    missing_spec_fields = sorted(REQUIRED_SPEC_FIELDS - set(first_spec))
    all_updates = [dict(spec.get("updates") or {}) for spec in specs]
    checks = {
        "family_method_exists": callable(getattr(family, "contracted_optimisation_ladder_specs", None)),
        "compatibility_alias_exists": callable(getattr(family, "contracted_repair_ladder_specs", None)),
        "contract_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_bending_overdesign_governs_runtime",
        "specs_present": bool(specs),
        "spec_shape_preserved": not missing_spec_fields,
        "specs_include_runtime_evidence": bool(first_spec.get("ladder_hash"))
        and bool(first_spec.get("update_hash"))
        and bool(first_spec.get("candidate_state_hash")),
        "restart_and_ranking_proof_present": any(spec.get("restart_proof") for spec in specs)
        and any(spec.get("ranking_proof") for spec in specs),
        "minimum_and_geometry_proof_present": bool(ladder.get("minimum_reinforcement_proof"))
        and bool(ladder.get("geometry_compliance_proof")),
        "updates_are_contract_owned_only": all(set(update) <= ALLOWED_UPDATE_KEYS for update in all_updates),
        "reinforcement_and_geometry_updates_present": any(
            ({"bot1_count", "db_bot_1"} <= set(update) or {"bot_row_1_bars", "bot_row_1_dia"} <= set(update))
            and ({"b", "bw"} & set(update) or "D" in update)
            for update in all_updates
        ),
        "api_identifies_runtime_authority": api_result.lock_proof.get("runtime_authority")
        == "run_bending_overdesign_governs_runtime"
        and "legacy_decision_authority" not in api_result.lock_proof,
        "contract_lane_order_preserved": tuple(api_result.evidence.get("contract_lane_order") or ())
        == bending_overdesign_contract_lane_order(),
        "inputs_page_still_owns_shared_plumbing": "from design_brain.cta_contracts import" in inputs_source
        and "from design_brain.publication import" in inputs_source
        and "build_design_guide_apply_button_contract" in inputs_source,
        "runtime_has_no_page_ui_imports": not forbidden_runtime_terms,
        "no_other_locked_family_imports": "bending_fail_governs" not in cleanup_source
        and "shear_fail_governs" not in cleanup_source
        and "shear_overdesign_governs" not in cleanup_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if missing_spec_fields:
        failures.append(f"missing_spec_fields:{missing_spec_fields}")
    if forbidden_runtime_terms:
        failures.append(f"forbidden_runtime_terms:{forbidden_runtime_terms}")
    snapshot = {
        "schema": "bending_overdesign_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "contract_lane_order": list(bending_overdesign_contract_lane_order()),
        "spec_count": len(specs),
        "first_spec": first_spec,
        "ladder_hash": ladder.get("ladder_hash"),
        "api_lock_proof": dict(api_result.lock_proof),
    }
    json_path, report_path = _write_artifacts(snapshot)
    if failures:
        print("BENDING_OVERDESIGN_GOVERNS cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("BENDING_OVERDESIGN_GOVERNS cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
