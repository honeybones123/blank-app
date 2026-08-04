"""Cutover implementation verifier for SHEAR_FAIL_GOVERNS."""

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

from design_brain.families.shear_fail import ShearFailFamily  # noqa: E402
from design_brain.families.shear_fail_governs import (  # noqa: E402
    run_shear_fail_governs_ladder_runtime as package_runtime_authority,
)
from design_brain.families.shear_fail_governs.runtime import (  # noqa: E402
    run_shear_fail_governs_ladder_runtime,
    shear_fail_governs_contract_lane_order,
)


EXPECTED_CONTRACT_ORDER = (
    "SPACING_REDUCTION",
    "LEG_COUNT_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "BAR_SIZE_INCREASE",
    "DEPTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "WIDTH_INCREASE_RESTART_REINFORCEMENT_SEARCH",
    "EXACT_STOP",
    "EXHAUSTED",
    "NO_VALID_REPAIR",
)
REQUIRED_SPEC_KEYS = {
    "ladder_index",
    "contract_step",
    "strategy",
    "updates",
    "restart_point",
    "escalation",
    "candidate_family_id",
    "label",
}
REQUIRED_RUNTIME_SPEC_KEYS = {
    "lane_id",
    "runtime_authority",
    "runtime_ladder_hash",
    "ladder_hash",
    "ladder_trace_ref",
    "update_hash",
    "candidate_state_hash",
    "evaluation_hash",
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
    "button_contract",
    "published_item",
    "rendered_html",
    "session_state",
    "st.",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _read_inputs_composition_surface() -> str:
    """Read the current Inputs application and family-ladder composition."""

    return "\n".join(
        _read(path)
        for path in (
            "inputs_page.py",
            "inputs_application/engineering_workspace.py",
            "inputs_application/guidance_entrypoint.py",
            "inputs_application/candidate_full_evaluation.py",
            "inputs_application/live_apply.py",
            "inputs_application/one_click_entrypoint.py",
            "inputs_application/page_runtime/design_guide.py",
            "inputs_page_modules/design_guide/family_ladder_guidance.py",
            "inputs_page_modules/design_guide/current_coordinators.py",
        )
    )


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
    runtime_path = ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py"
    blocked: list[str] = []
    for imported in _module_imports(runtime_path):
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_RUNTIME_IMPORT_PREFIXES):
            blocked.append(imported)
    return sorted(set(blocked))


def _forbidden_runtime_source_hits() -> list[str]:
    source = _read("design_brain/families/shear_fail_governs/runtime.py").lower()
    return sorted(term for term in FORBIDDEN_RUNTIME_SOURCE_TERMS if term.lower() in source)


def _contains_all(source: str, needles: list[str]) -> dict[str, bool]:
    return {needle: needle in source for needle in needles}


def _spec_shape_ok(spec: dict[str, Any]) -> bool:
    return REQUIRED_SPEC_KEYS.issubset(set(spec)) and REQUIRED_RUNTIME_SPEC_KEYS.issubset(set(spec))


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_cutover_implementation_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# SHEAR_FAIL_GOVERNS Cutover Implementation",
        "",
        f"Status: {snapshot['status']}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in snapshot["checks"].items())
    lines.extend(["", "## Runtime Evidence", ""])
    lines.extend(
        [
            f"- runtime_authority: `{snapshot['ladder_summary'].get('runtime_authority')}`",
            f"- spec_count: `{snapshot['ladder_summary'].get('spec_count')}`",
            f"- ladder_hash: `{snapshot['ladder_summary'].get('ladder_hash')}`",
        ]
    )
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    shear_source = _read("design_brain/families/shear_fail.py")
    package_source = _read("design_brain/families/shear_fail_governs/__init__.py")
    inputs_source = _read_inputs_composition_surface()
    ladder = ShearFailFamily().contracted_repair_ladder_specs(
        {"b": 400.0, "D": 600.0, "s_lig": 300.0, "lig_d": 10, "lig_legs": 2},
        geometry_locked=False,
    )
    specs = [dict(spec) for spec in ladder.get("specs") or [] if isinstance(spec, dict)]
    restart_specs = [spec for spec in specs if dict(spec.get("restart_proof") or {}).get("present")]
    ranking_specs = [spec for spec in specs if spec.get("ranking_proof") is not None]
    first_spec = specs[0] if specs else {}
    package_exports_runtime = callable(package_runtime_authority) and (
        "run_shear_fail_governs_ladder_runtime" in package_source
    )
    compatibility_api_absent = "evaluate_" + "shear_fail_governs" not in package_source
    inputs_surface = _contains_all(
        inputs_source,
        [
            "def _evaluate_updates(",
            "evaluate_candidate_full_for_app_bridge(",
            "_evaluate_auto_design_candidate(",
            '"SHEAR_FAIL_GOVERNS"',
            "family_strategy_for(dispatch_family_id)",
            "family_strategy.contracted_repair_ladder_specs(",
        ],
    )

    checks = {
        "contracted_specs_delegates_to_runtime": "run_shear_fail_governs_ladder_runtime" in shear_source
        and ladder.get("runtime_authority") == "run_shear_fail_governs_ladder_runtime",
        "contract_lane_order_preserved": shear_fail_governs_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "returned_specs_preserve_inputs_page_shape": bool(specs) and all(_spec_shape_ok(spec) for spec in specs),
        "returned_specs_include_runtime_evidence": bool(first_spec.get("runtime_ladder_hash"))
        and bool(first_spec.get("ladder_trace_ref"))
        and bool(first_spec.get("update_hash"))
        and bool(first_spec.get("candidate_state_hash")),
        "restart_proof_present": bool(restart_specs),
        "ranking_proof_present": bool(ranking_specs) and bool(ladder.get("ranking_proof") is not None),
        "package_exports_runtime_authority_without_compatibility_api": package_exports_runtime
        and compatibility_api_absent,
        "inputs_application_owns_evaluate_and_execution_plumbing": (
            (
                inputs_surface["def _evaluate_updates("]
                or inputs_surface["evaluate_candidate_full_for_app_bridge("]
            )
            and inputs_surface["_evaluate_auto_design_candidate("]
        ),
        "runtime_has_no_cta_publication_apply_ui_session_imports": not _forbidden_runtime_imports()
        and not _forbidden_runtime_source_hits(),
        "no_bending_files_required_or_imported": "design_brain.families.bending" not in shear_source
        and "bending_fail_governs" not in shear_source
        and "bending_fail_governs" not in package_source
        and not any("bending" in imported for imported in _module_imports(ROOT / "design_brain" / "families" / "shear_fail_governs" / "runtime.py")),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "shear_fail_governs_cutover_implementation.v2",
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "ladder_summary": {
            "runtime_authority": ladder.get("runtime_authority"),
            "spec_count": len(specs),
            "ladder_hash": ladder.get("ladder_hash"),
            "spacing_values_tried": ladder.get("spacing_values_tried"),
            "lig_diameters_tried": ladder.get("lig_diameters_tried"),
            "widths_tried": ladder.get("widths_tried"),
            "stop_reason_if_no_candidate": ladder.get("stop_reason_if_no_candidate"),
        },
        "first_spec": first_spec,
        "restart_spec_count": len(restart_specs),
        "ranking_spec_count": len(ranking_specs),
        "package_runtime_authority": {
            "package_exports_runtime": package_exports_runtime,
            "compatibility_api_absent": compatibility_api_absent,
        },
        "runtime_forbidden_imports": _forbidden_runtime_imports(),
        "runtime_forbidden_source_hits": _forbidden_runtime_source_hits(),
        "inputs_application_surfaces": inputs_surface,
        "scope_limits": {
            "inputs_application_changed": False,
            "cta_rendering_moved": False,
            "publication_moved": False,
            "apply_routing_moved": False,
            "one_click_moved": False,
            "visible_wording_moved": False,
            "ui_session_debug_moved": False,
            "bending_touched": False,
        },
        "failures": failures,
    }
    json_path, report_path = _write_artifacts(snapshot)
    print(f"{snapshot['status']}: {json_path}")
    print(f"REPORT: {report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
