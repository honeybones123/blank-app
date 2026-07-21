"""Cutover implementation verifier for COMBINED_BENDING_SHEAR_FAIL_GOVERNS."""

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

from design_brain.combined_bending_shear_candidate_merge import CombinedBendingShearFailInputs  # noqa: E402
from design_brain.families.bending_and_shear_fail_govern import run_combined_bending_shear_fail_runtime  # noqa: E402
from design_brain.families.combined_bending_shear_fail import (  # noqa: E402
    CombinedBendingShearFailFamily,
    _default_runtime_evaluator,
)


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


def _source_candidates() -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    return (
        (
            {
                "source_family_id": "BENDING_FAIL_GOVERNS",
                "candidate_id": "bend_depth",
                "updates": {"D": 550.0, "bot_row_1_bars": 5, "bot_row_1_dia": 20},
            },
        ),
        ({"source_family_id": "SHEAR_FAIL_GOVERNS", "candidate_id": "shear_links", "updates": {"lig_d": 12}},),
    )


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_BENDING_SHEAR_FAIL_GOVERNS Cutover Implementation",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    bending, shear = _source_candidates()
    family = CombinedBendingShearFailFamily()
    ladder = family.contracted_repair_ladder_specs(
        {"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        bending_fail_candidates=bending,
        shear_fail_candidates=shear,
    )
    runtime_result = run_combined_bending_shear_fail_runtime(
        inputs=CombinedBendingShearFailInputs(
            selected_family_id="COMBINED_BENDING_SHEAR_FAIL",
            base_state={"selected_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
            bending_fail_candidates=bending,
            shear_fail_candidates=shear,
        ),
        evaluate_candidate=_default_runtime_evaluator,
    )
    specs = [dict(spec) for spec in list(ladder.get("specs") or []) if isinstance(spec, dict)]
    first = specs[0] if specs else {}
    family_source = (ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py").read_text(encoding="utf-8", errors="replace")
    inputs_source = _read_inputs_composition_surface()
    checks = {
        "contract_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_combined_bending_shear_fail_runtime",
        "legacy_ladder_constants_removed": "DEFAULT_DEPTH_STEPS_MM" not in family_source
        and "DEFAULT_WIDTH_STEPS_MM" not in family_source,
        "specs_present": bool(specs),
        "specs_include_runtime_evidence": bool(first.get("runtime_hash"))
        and bool(first.get("candidate_source_proof"))
        and bool(first.get("ranking_evidence")),
        "family_boundary_emits_canonical_updates": {"bot_row_1_bars", "bot_row_1_dia"} <= set(dict(first.get("updates") or {}))
        and "bot1_count" not in set(dict(first.get("updates") or {})),
        "source_family_ids_preserved": set(first.get("source_family_ids") or ())
        == {"BENDING_FAIL_GOVERNS", "SHEAR_FAIL_GOVERNS"},
        "package_runtime_export_matches_family_shell": runtime_result.runtime_hash == ladder.get("runtime_hash"),
        "family_shell_keeps_shared_outputs_outside": "shared_system_owned_outside_family" in family_source,
        "inputs_page_not_modified_for_cutover": "combined_fail_contract_ladder" in inputs_source,
        "route_existing_decision_no_longer_claims_used": "'family_routing_used': True" not in family_source
        and '"family_routing_used": True' not in family_source
        and "combined family lock keeps shared routing outside family" in family_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "spec_count": len(specs),
        "first_spec": first,
        "runtime_hash": ladder.get("runtime_hash"),
        "runtime_result": runtime_result.to_dict(),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_BENDING_SHEAR_FAIL_GOVERNS cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
