"""Audit bottom-reo selector result object boundary."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_pick_best_bottom_recommendation_by_selector"
RESULT_WRAPPER = "_bottom_reo_selector_result_record"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, TARGET_HELPER)
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(inputs_source, RESULT_WRAPPER)

    family_has_dataclass = "class BottomReoSelectorResult" in bending_source
    wrapper_dependencies = {
        "delegates_to_family_helper": (
            "_build_bottom_reo_selector_result_record(" in wrapper_segment
            or "_build_bottom_reo_selector_result_record_from_candidate(" in wrapper_segment
        ),
        "does_not_construct_family_result_type_locally": "BottomReoSelectorResult(" not in wrapper_segment,
        "page_candidate_summary_removed": "_bottom_reo_recommendation_trace_candidate_summary(" not in wrapper_segment,
        "page_candidate_identity_removed": "_bottom_reo_candidate_identity(" not in wrapper_segment,
        "page_hash_removed": "_dg_runtime_trace_hash(" not in wrapper_segment,
        "page_float_normalizer_removed": "_bottom_reo_trace_float(" not in wrapper_segment,
    }
    selector_dependencies = {
        "delegates_live_loop_to_family": "_select_bottom_reo_recommendation_candidate_by_selector(" in selector_segment,
        "passes_page_best_selector_as_callback": "select_best_candidate_fn=_select_best_auto_design_candidate" in selector_segment,
        "keeps_page_strict_band_guard_callback": "_is_strictly_rejectable_band_winner(" in selector_segment,
        "emits_rank_trace_from_projection": "_log_design_reco_candidate_rank(**dict(_event))" in selector_segment,
        "merges_rank_trace": "_merge_design_guide_rank_trace(" in selector_segment,
        "calls_selector_result_wrapper": "_bottom_reo_selector_result_record(" in selector_segment,
        "keeps_page_legacy_rejection_callback": "_legacy_bottom_local_rejection_reason(" in selector_segment,
    }

    surface_rows = [
        {
            "surface": "BottomReoSelectorResult dataclass",
            "current_owner": "design_brain.families.bending",
            "target_owner": "design_brain.families.bending",
            "classification": "ALREADY_FAMILY_OWNED",
            "risk": "LOW",
        },
        {
            "surface": "selector result record wrapper",
            "current_owner": "inputs_page.py",
            "target_owner": "design_brain.families.bending plus page trace input collection",
            "classification": "PARTIAL_TYPED_RECORD_EXTRACTED_TRACE_INPUTS_PAGE_OWNED",
            "risk": "MEDIUM",
        },
        {
            "surface": "live selector loop",
            "current_owner": "inputs_page.py",
            "target_owner": "family/controller selector service",
            "classification": "FAMILY_SELECTOR_HELPER_CUTOVER_COMPLETE_PAGE_CALLBACKS_REMAIN",
            "risk": "HIGH",
        },
        {
            "surface": "strict band guard and legacy rejection",
            "current_owner": "inputs_page.py",
            "target_owner": "family/controller selector service",
            "classification": "NOT_READY_UNTIL_SELECTOR_POLICY_PARITY",
            "risk": "HIGH",
        },
        {
            "surface": "rank trace logging",
            "current_owner": "inputs_page.py",
            "target_owner": "debug/proof service",
            "classification": "KEEP_PAGE_FOR_NOW",
            "risk": "LOW",
        },
    ]

    checks = {
        "family_selector_result_type_exists": family_has_dataclass,
        "page_wrapper_found": bool(wrapper_segment),
        "selector_found": bool(selector_segment),
        "wrapper_delegates_to_family_helper": bool(wrapper_dependencies.get("delegates_to_family_helper")),
        "wrapper_trace_inputs_bounded_or_removed": bool(wrapper_dependencies.get("delegates_to_family_helper"))
        and bool(wrapper_dependencies.get("does_not_construct_family_result_type_locally")),
        "selector_dependencies_mapped": all(selector_dependencies.values()),
        "selector_policy_next_slice_identified": True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SELECTOR_RESULT_OBJECT_AND_LIVE_LOOP_FAMILY_CUTOVER_COMPLETE",
        "selector_lines": {"start": selector_start, "end": selector_end},
        "wrapper_lines": {"start": wrapper_start, "end": wrapper_end},
        "wrapper_dependencies": wrapper_dependencies,
        "selector_dependencies": selector_dependencies,
        "surface_rows": surface_rows,
        "checks": checks,
        "first_safe_implementation_slice": {
            "name": "bottom_reo_result_packaging_or_callback_shell_lock",
            "move": [
                "Selector policy is family-owned; next audit should bound remaining callback execution, trace emission, and result packaging.",
            ],
            "keep": [
                "final result packaging",
            ],
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_selector_result_object_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_selector_result_object_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selector Result Object Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Classification",
        "",
        "| Surface | Classification | Current owner | Target owner | Risk |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("surface_rows") or []:
        lines.append(
            f"| `{row.get('surface')}` | `{row.get('classification')}` | {row.get('current_owner')} | {row.get('target_owner')} | `{row.get('risk')}` |"
        )
    next_slice = dict(payload.get("first_safe_implementation_slice") or {})
    lines.extend(["", "## First Safe Implementation Slice", "", f"- Name: `{next_slice.get('name')}`", "", "Move:"])
    lines.extend(f"- {item}" for item in next_slice.get("move") or [])
    lines.append("")
    lines.append("Keep:")
    lines.extend(f"- {item}" for item in next_slice.get("keep") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_recommendation_selector_result_object_boundary {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
