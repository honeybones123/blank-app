from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


SURFACES: tuple[dict[str, Any], ...] = (
    {
        "surface": "pure_calculation_modules",
        "functions": [],
        "files": [
            "calculations/bending.py",
            "calculations/shear.py",
            "calculations/crack_control.py",
            "calculations/deflection.py",
            "calculations/design_actions.py",
            "calculations/materials.py",
            "calculations/shear_zone_spacing.py",
        ],
        "current_owner": "calculations/*",
        "target_owner": "calculations/*",
        "classification": "already_module_owned",
        "extraction_readiness": "LOCKED_OUT_OF_SCOPE_FOR_THIS_SLICE",
        "risk": "LOW",
        "notes": "Engineering calculations are already outside inputs_page.py and covered by calculation-module parity verifiers.",
    },
    {
        "surface": "bending_detailed_explainer_rendering",
        "functions": [],
        "files": ["bending_tabs.py"],
        "current_owner": "bending_tabs.py",
        "target_owner": "inputs_page_modules/calculations",
        "classification": "shared_render_helper_with_calcbox_steps",
        "extraction_readiness": "AUDIT_ONLY_NOT_READY",
        "risk": "MEDIUM",
        "notes": "Bending detailed check step cards are already outside inputs_page.py, but not yet in the target calculations module boundary.",
    },
    {
        "surface": "crack_detailed_explainer_rendering",
        "functions": [],
        "files": ["crack_page.py"],
        "current_owner": "crack_page.py",
        "target_owner": "inputs_page_modules/calculations",
        "classification": "shared_render_helper_with_calcbox_steps",
        "extraction_readiness": "AUDIT_ONLY_NOT_READY",
        "risk": "MEDIUM",
        "notes": "Crack detailed cards are page-render helpers and should be audited before any move.",
    },
    {
        "surface": "deflection_detailed_explainer_rendering",
        "functions": [],
        "files": ["deflection.py"],
        "current_owner": "deflection.py",
        "target_owner": "inputs_page_modules/calculations",
        "classification": "shared_render_helper_with_calcbox_steps",
        "extraction_readiness": "AUDIT_ONLY_NOT_READY",
        "risk": "MEDIUM",
        "notes": "Deflection detailed render and load-state messaging should move only after typed view-model parity.",
    },
    {
        "surface": "inputs_overview_pack_construction",
        "functions": [
            "_build_crack_pack_from_state",
            "_build_deflection_pack_from_state",
            "_collect_design_overview",
        ],
        "files": ["inputs_page.py"],
        "current_owner": "inputs_page.py",
        "target_owner": "calculation/explainer view-model service or existing summary service boundary",
        "classification": "page_owned_state_packaging",
        "extraction_readiness": "READY_FOR_TYPED_TRACE",
        "risk": "HIGH",
        "notes": "These helpers bridge authoritative results into summary/Design Guide packs; move only with strict parity because they also feed non-calculation consumers.",
    },
    {
        "surface": "inputs_summary_detail_expansion_models",
        "functions": [
            "_normalise_row",
            "_primary_row",
            "_overall_status_from_rows",
        ],
        "files": ["inputs_page.py", "inputs_page_modules/summaries/*", "ui/summary_sections.py"],
        "current_owner": "mixed",
        "target_owner": "inputs_page_modules/calculations or summaries depending on consumer",
        "classification": "duplicated_display_normalisation_boundary",
        "extraction_readiness": "NEEDS_PARITY_WITH_SUMMARY_MODULE",
        "risk": "MEDIUM",
        "notes": "Some summary display logic has moved; remaining calculation expansion row logic must be separated from summary-card ownership before extraction.",
    },
    {
        "surface": "legacy_unreachable_summary_detail_renderer",
        "functions": ["_render_inputs_summary_expanders_and_tables"],
        "files": ["inputs_page.py"],
        "current_owner": "inputs_page.py",
        "target_owner": "delete_after_deadness_or move renderer-only fragments",
        "classification": "post_return_legacy_renderer_tail",
        "extraction_readiness": "DEADNESS_PROOF_REQUIRED",
        "risk": "MEDIUM",
        "notes": "There is a large renderer tail after an early return in the summary renderer region. Treat as deletion candidate only after a focused deadness verifier.",
    },
    {
        "surface": "widget_calcbox_and_info_helpers",
        "functions": [],
        "files": ["widgets_helpers.py", "ui_seamless_steps.py"],
        "current_owner": "shared_ui_helpers",
        "target_owner": "shared_ui_helpers",
        "classification": "renderer_style_helpers",
        "extraction_readiness": "SHELL_ONLY",
        "risk": "LOW",
        "notes": "These are UI primitives; calculations module should build view models, not own Streamlit rendering primitives.",
    },
)


EXISTING_VERIFIERS = (
    "tools/verification/bending_calculation_module_parity.py",
    "tools/verification/shear_calculation_module_parity.py",
    "tools/verification/crack_calculation_module_parity.py",
    "tools/verification/deflection_calculation_module_parity.py",
    "tools/verification/design_actions_calculation_module_parity.py",
    "tools/verification/shear_zone_spacing_calculation_module_parity.py",
    "tools/verification/summary_sections_smoke.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_ranges(source: str) -> dict[str, dict[str, int]]:
    tree = ast.parse(source)
    out: dict[str, dict[str, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = {
                "start": int(node.lineno),
                "end": int(getattr(node, "end_lineno", node.lineno)),
            }
    return out


def _file_status(path: str) -> dict[str, Any]:
    if "*" in path:
        return {"path": path, "exists": True, "kind": "glob_reference"}
    p = ROOT / path
    return {"path": path, "exists": p.exists(), "kind": "file"}


def _augment_surfaces() -> list[dict[str, Any]]:
    source = _read(INPUTS_PAGE)
    ranges = _function_ranges(source)
    augmented: list[dict[str, Any]] = []
    for surface in SURFACES:
        entry = dict(surface)
        entry["files"] = [_file_status(path) for path in surface["files"]]
        entry["function_ranges"] = {
            name: ranges.get(name)
            for name in surface.get("functions", ())
            if name in ranges
        }
        entry["missing_functions"] = [
            name
            for name in surface.get("functions", ())
            if name not in ranges
        ]
        entry["changes_engineering_outcome"] = surface["classification"] in {
            "page_owned_state_packaging",
        }
        entry["changes_visible_wording"] = surface["classification"] in {
            "shared_render_helper_with_calcbox_steps",
            "duplicated_display_normalisation_boundary",
            "post_return_legacy_renderer_tail",
        }
        entry["changes_cta_apply"] = False
        entry["writes_session_debug"] = surface["surface"] in {
            "inputs_overview_pack_construction",
            "legacy_unreachable_summary_detail_renderer",
        }
        augmented.append(entry)
    return augmented


def _existing_verifier_status() -> list[dict[str, Any]]:
    return [
        {
            "path": verifier,
            "exists": (ROOT / verifier).exists(),
        }
        for verifier in EXISTING_VERIFIERS
    ]


def _decision(surfaces: list[dict[str, Any]]) -> str:
    if any(any(not f["exists"] for f in row["files"]) for row in surfaces):
        return "CALCULATION_EXPLAINER_AUTHORITY_AMBIGUOUS"
    if any(row["missing_functions"] for row in surfaces):
        return "CALCULATION_EXPLAINER_AUTHORITY_AMBIGUOUS"
    return "READY_FOR_CALCULATION_TYPED_MODEL_TRACE"


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines: list[str] = []
    lines.append("# Inputs Calculations & Explainers Phase 0 Ownership Audit")
    lines.append("")
    lines.append(f"## Executive Summary: {payload['decision']}")
    lines.append("")
    lines.append("This is audit-only. No product behavior, wording, CTA/apply, or rendering was changed.")
    lines.append("")
    lines.append("## Current State")
    lines.append("")
    lines.append("- Pure engineering calculations are already module-owned under `calculations/*`.")
    lines.append("- Inputs still owns some state-packaging and display-normalisation bridges used by summaries and Design Guide.")
    lines.append("- Detailed check/explainer render helpers exist outside `inputs_page.py`, but not yet under the target `inputs_page_modules/calculations/` boundary.")
    lines.append("- A typed trace/parity slice is required before moving any live calculation/explainer presentation model.")
    lines.append("")
    lines.append("## Surface Inventory")
    lines.append("")
    lines.append("| Surface | Current owner | Target owner | Classification | Readiness | Risk | Lines |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in payload["surfaces"]:
        ranges = ", ".join(
            f"`{name}`:{rng['start']}-{rng['end']}"
            for name, rng in row["function_ranges"].items()
            if rng
        ) or "-"
        lines.append(
            "| {surface} | {current_owner} | {target_owner} | {classification} | {extraction_readiness} | {risk} | {ranges} |".format(
                ranges=ranges,
                **row,
            )
        )
    lines.append("")
    lines.append("## Existing Verifiers")
    lines.append("")
    for verifier in payload["existing_verifiers"]:
        status = "present" if verifier["exists"] else "missing"
        lines.append(f"- `{verifier['path']}`: {status}")
    lines.append("")
    lines.append("## First Safe Implementation Slice")
    lines.append("")
    lines.append("Create `inputs_page_modules/calculations/` with typed source snapshots and view models for calculation/explainer presentation only. Run it trace-only beside the current page/shared render path and compare hashes/visible text before any delegation.")
    lines.append("")
    lines.append("## Stop Conditions")
    lines.append("")
    lines.append("- Any engineering value changes.")
    lines.append("- Any detailed-check wording changes.")
    lines.append("- Any status/tone/order mismatch.")
    lines.append("- Any Streamlit/session import enters the extracted calculations builder.")
    lines.append("- Any Design Guide CTA/apply behavior changes.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    surfaces = _augment_surfaces()
    payload: dict[str, Any] = {
        "audit": "inputs_calculations_phase0_ownership_audit",
        "timestamp": timestamp,
        "decision": _decision(surfaces),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "surfaces": surfaces,
        "existing_verifiers": _existing_verifier_status(),
        "first_safe_slice": "typed_trace_parity_for_calculation_explainer_presentation_models",
    }
    json_path = VERIFICATION_DIR / f"inputs_calculations_phase0_ownership_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_phase0_ownership_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"inputs_calculations_phase0_ownership_audit PASS")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
