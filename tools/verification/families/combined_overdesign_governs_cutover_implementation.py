"""Cutover implementation verifier for COMBINED_OVERDESIGN_GOVERNS."""

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

from design_brain.families.bending_and_shear_overdesign_govern import (  # noqa: E402
    evaluate_bending_and_shear_overdesign_govern,
)
from design_brain.families.combined_cleanup import CombinedCleanupFamily  # noqa: E402


def _sources() -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    return (
        (
            {
                "source_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "candidate_id": "bend_cleanup",
                "updates": {"bot1_count": 4, "db_bot_1": 20},
            },
        ),
        (
            {
                "source_family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "candidate_id": "remove_links",
                "updates": {"lig_d": 0, "lig_legs": 0},
            },
        ),
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


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_overdesign_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_overdesign_governs_cutover_implementation_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# COMBINED_OVERDESIGN_GOVERNS Cutover Implementation",
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
    bending, shear = _sources()
    family = CombinedCleanupFamily()
    ladder = family.contracted_optimisation_ladder_specs(
        {"b": 300.0, "D": 500.0, "As": 2260.0, "As_min": 950.0, "Vstar": 0.0},
        bending_overdesign_candidates=bending,
        shear_overdesign_candidates=shear,
    )
    api_result = evaluate_bending_and_shear_overdesign_govern(
        {
            "state": {"b": 300.0, "D": 500.0, "As": 2260.0, "As_min": 950.0, "Vstar": 0.0},
            "bending_overdesign_candidates": bending,
            "shear_overdesign_candidates": shear,
        }
    )
    shell_source = _read("design_brain/families/combined_cleanup.py")
    runtime_source = _read("design_brain/families/bending_and_shear_overdesign_govern/runtime.py")
    inputs_source = _read_inputs_composition_surface()
    publication_source = _read("design_brain/publication.py")
    specs = list(ladder.get("specs") or [])
    first = dict(specs[0]) if specs else {}
    checks = {
        "family_method_exists": callable(getattr(family, "contracted_optimisation_ladder_specs", None)),
        "compatibility_alias_exists": callable(getattr(family, "contracted_repair_ladder_specs", None)),
        "family_shell_runtime_driven": ladder.get("contract_runtime_driven") is True
        and ladder.get("contract_runtime_authority") == "run_combined_overdesign_governs_runtime",
        "specs_preserve_source_evidence": bool(first.get("source_family_ids"))
        and set(first.get("source_family_ids") or ()) == {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS"}
        and bool(first.get("update_hash"))
        and bool(first.get("candidate_state_hash")),
        "api_identifies_runtime_authority": api_result.lock_proof.get("runtime_authority")
        == "run_combined_overdesign_governs_runtime",
        "api_does_not_publish_or_generate_cta": api_result.publication == {} and api_result.cta_contract == {},
        "combined_shell_does_not_call_source_runtimes": "run_bending_overdesign_governs_runtime" not in shell_source
        and "run_shear_overdesign_governs_runtime" not in shell_source,
        "runtime_does_not_call_source_runtimes": "run_bending_overdesign_governs_runtime" not in runtime_source
        and "run_shear_overdesign_governs_runtime" not in runtime_source,
        "inputs_page_not_modified_as_cutover_surface": (
            "FinalDesignGuidePublication" in inputs_source
            or "build_final_design_guide_publication" in inputs_source
        )
        and (
            "_design_guide_apply_button_contracts_to_items" in inputs_source
            or "build_design_guide_apply_button_contract_inputs" in publication_source
        ),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_overdesign_governs_cutover_implementation.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "ladder": {
            "spec_count": len(specs),
            "runtime_hash": ladder.get("runtime_hash"),
            "selected_recommendation": ladder.get("selected_recommendation"),
        },
        "api_lock_proof": dict(api_result.lock_proof),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("COMBINED_OVERDESIGN_GOVERNS cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("COMBINED_OVERDESIGN_GOVERNS cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
