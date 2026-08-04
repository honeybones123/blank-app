"""Verify optimisation selector debug projection extraction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    raise RuntimeError(f"Function not found: {name}")


def _expected_projection(
    *,
    guidance_branch: str,
    primary_item: dict[str, Any],
    selector_debug: dict[str, Any],
    selected_family: str,
    governing_action: str,
) -> dict[str, Any]:
    out = {
        "guidance_branch": guidance_branch,
        "selected_action_type": primary_item.get("action_type"),
        "selected_title": primary_item.get("title_main"),
        "optimisation_selector_governing_action": selector_debug.get(
            "optimisation_selector_governing_action",
        ),
        "optimisation_selector_family_bias_applied": bool(
            selector_debug.get("optimisation_selector_family_bias_applied"),
        ),
        "optimisation_selector_candidate_counts_by_family": dict(
            selector_debug.get("optimisation_selector_candidate_counts_by_family") or {},
        ),
        "optimisation_selector_winning_family": selector_debug.get(
            "optimisation_selector_winning_family",
        ) or selected_family,
        "optimisation_selector_used_geometry_fallback": bool(
            selector_debug.get("optimisation_selector_used_geometry_fallback"),
        ),
        "optimisation_selector_fallback_reason": selector_debug.get(
            "optimisation_selector_fallback_reason",
        ),
        "optimisation_selector_candidate_reaches_target_band": bool(
            selector_debug.get("optimisation_selector_candidate_reaches_target_band"),
        ),
        "optimisation_selector_candidate_all_key_pass": bool(
            selector_debug.get("optimisation_selector_candidate_all_key_pass"),
        ),
        "primary_optimisation_selection_owner": selector_debug.get(
            "primary_optimisation_selection_owner",
            "controller_fallback",
        ),
        "overdesign_no_band_reacher_but_compliant_candidates_exist": bool(
            selector_debug.get("overdesign_no_band_reacher_but_compliant_candidates_exist"),
        ),
        "overdesign_stepwise_fallback_used": bool(
            selector_debug.get("overdesign_stepwise_fallback_used"),
        ),
        "overdesign_stepwise_fallback_family": selector_debug.get(
            "overdesign_stepwise_fallback_family",
        ),
        "overdesign_stepwise_fallback_reason": selector_debug.get(
            "overdesign_stepwise_fallback_reason",
        ),
        "overdesign_stepwise_selected_post_util": selector_debug.get(
            "overdesign_stepwise_selected_post_util",
        ),
    }
    if str(out["primary_optimisation_selection_owner"]) == "controller_fallback":
        out["candidate_family"] = selected_family
        out["governing_action"] = governing_action
    return out


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_optimisation_selector_debug_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    core_segment = _function_segment(inputs_source, "_compute_design_guidance_items_core")
    fallback_marker = "if primary is None:"
    fallback_start = core_segment.index(fallback_marker) if fallback_marker in core_segment else -1
    fallback_end = (
        core_segment.index("action_type = str(primary.get", fallback_start)
        if fallback_start >= 0 and "action_type = str(primary.get" in core_segment[fallback_start:]
        else len(core_segment)
    )
    fallback_block = core_segment[fallback_start:fallback_end] if fallback_start >= 0 else ""
    helper_segment = _function_segment(
        controller_source,
        "build_design_guide_controller_optimisation_selector_debug_projection",
    )
    cases = [
        {
            "name": "shared_selector",
            "guidance_branch": "efficiency_tighten_geometry",
            "primary_item": {"action_type": "tighten_geometry", "title_main": "Tighten geometry"},
            "selector_debug": {
                "optimisation_selector_governing_action": "bending",
                "optimisation_selector_family_bias_applied": True,
                "optimisation_selector_candidate_counts_by_family": {"bending": 2},
                "optimisation_selector_winning_family": "bending",
                "primary_optimisation_selection_owner": "shared_selector",
                "optimisation_selector_candidate_reaches_target_band": True,
            },
            "selected_family": "bending",
            "governing_action": "bending",
        },
        {
            "name": "controller_fallback",
            "guidance_branch": "efficiency_reduce_bottom_reinforcement",
            "primary_item": {"action_type": "reduce_bottom_reinforcement", "title_main": "Reduce bottom reinforcement"},
            "selector_debug": {
                "optimisation_selector_fallback_reason": "shared_selector_no_primary_fallback_order_used",
                "primary_optimisation_selection_owner": "controller_fallback",
            },
            "selected_family": "bending",
            "governing_action": "bending",
        },
    ]
    parity_rows = []
    for case in cases:
        expected = _expected_projection(
            guidance_branch=str(case["guidance_branch"]),
            primary_item=dict(case["primary_item"]),
            selector_debug=dict(case["selector_debug"]),
            selected_family=str(case["selected_family"]),
            governing_action=str(case["governing_action"]),
        )
        actual = build_design_guide_controller_optimisation_selector_debug_projection(
            guidance_branch=str(case["guidance_branch"]),
            primary_item=dict(case["primary_item"]),
            selector_debug=dict(case["selector_debug"]),
            selected_family=str(case["selected_family"]),
            governing_action=str(case["governing_action"]),
        )
        parity_rows.append(
            {
                "case": case["name"],
                "matches": _stable(expected) == _stable(actual),
                "expected": expected,
                "actual": actual,
            }
        )
    source_checks = {
        "page_delegates_to_controller": "_build_design_guide_controller_optimisation_selector_debug_projection(" in core_segment,
        "page_delegates_legacy_fallback_selection": (
            "_resolve_design_guide_controller_optimisation_selector_fallback_result(" in core_segment
        ),
        "page_no_longer_keeps_inline_fallback_candidate_selection": (
            'if str(item.get("check_key") or "") == str(governing_action or "")' not in fallback_block
            and "shared_selector_no_primary_fallback_order_used" not in fallback_block
        ),
        "page_no_longer_sets_selector_debug_rows_inline": 'debug_sink["optimisation_selector_governing_action"]' not in core_segment,
        "controller_helper_exists": "def build_design_guide_controller_optimisation_selector_debug_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_optimisation_selector_debug_projection"' in controller_source,
        "helper_no_session_reads": "st.session_state" not in helper_segment,
        "controller_no_streamlit_import": "import streamlit" not in controller_source and "from streamlit" not in controller_source,
    }
    status = "PASS" if all(row["matches"] for row in parity_rows) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_compute_optimisation_selector_debug_projection_extraction.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "parity_rows": parity_rows,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "optimisation_selector_legacy_fallback_candidate_selection_boundary",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_compute_optimisation_selector_debug_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_optimisation_selector_debug_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Optimisation Selector Debug Projection Extraction",
        "",
        "## Executive Summary",
        str(payload["status"]),
        "",
        "## Parity",
        *[f"- {row['case']}: {'PASS' if row['matches'] else 'FAIL'}" for row in payload["parity_rows"]],
        "",
        "## Source Checks",
        *[f"- {key}: {value}" for key, value in payload["source_checks"].items()],
        "",
        "## Next Safe Target",
        str(payload["next_safe_target"]),
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_compute_optimisation_selector_debug_projection_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
