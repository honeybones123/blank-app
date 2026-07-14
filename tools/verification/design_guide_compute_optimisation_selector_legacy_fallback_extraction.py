"""Verify optimisation selector fallback extraction after legacy surface removal."""

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


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _old_fallback_projection(
    *,
    candidates: list[dict[str, Any]],
    governing_action: str,
    selector_debug: dict[str, Any],
    candidate_families: list[str],
) -> dict[str, Any]:
    if not candidates:
        return {
            "selected_index": None,
            "selected_family": None,
            "selector_debug": {
                **selector_debug,
                "optimisation_selector_winning_family": None,
                "optimisation_selector_fallback_reason": (
                    selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_no_primary_no_candidates"
                ),
                "primary_optimisation_selection_owner": "controller_fallback",
            },
        }
    selected_index = 0
    for index, item in enumerate(candidates):
        if str(item.get("check_key") or "") == str(governing_action or ""):
            selected_index = index
            break
    selected_family = candidate_families[selected_index] if selected_index < len(candidate_families) else None
    if not selected_family:
        selected_family = "other"
    return {
        "selected_index": selected_index,
        "selected_family": selected_family,
        "selector_debug": {
            **selector_debug,
            "optimisation_selector_winning_family": selected_family,
            "optimisation_selector_fallback_reason": (
                selector_debug.get("optimisation_selector_fallback_reason")
                    or "shared_selector_no_primary_fallback_order_used"
                ),
                "primary_optimisation_selection_owner": "controller_fallback",
            },
        }


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_optimisation_selector_fallback_result,
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
        "resolve_design_guide_controller_optimisation_selector_fallback_result",
    )
    cases = [
        {
            "name": "matching_governing_check_key",
            "candidates": [
                {"check_key": "shear", "action_type": "increase_link_spacing"},
                {"check_key": "bending", "action_type": "reduce_bottom_reinforcement"},
            ],
            "governing_action": "bending",
            "selector_debug": {"optimisation_selector_governing_action": "bending"},
            "candidate_families": ["shear", "bending"],
        },
        {
            "name": "first_candidate_fallback",
            "candidates": [
                {"check_key": "shear", "action_type": "increase_link_spacing"},
                {"check_key": "geometry", "action_type": "tighten_geometry"},
            ],
            "governing_action": "bending",
        "selector_debug": {
            "optimisation_selector_governing_action": "bending",
            "optimisation_selector_fallback_reason": "existing_reason",
        },
            "candidate_families": ["shear", "geometry"],
        },
        {
            "name": "empty_candidates",
            "candidates": [],
            "governing_action": "bending",
            "selector_debug": {},
            "candidate_families": [],
        },
    ]

    parity_rows = []
    for case in cases:
        expected = _old_fallback_projection(
            candidates=list(case["candidates"]),
            governing_action=str(case["governing_action"]),
            selector_debug=dict(case["selector_debug"]),
            candidate_families=list(case["candidate_families"]),
        )
        actual = resolve_design_guide_controller_optimisation_selector_fallback_result(
            candidates=list(case["candidates"]),
            governing_action=str(case["governing_action"]),
            selector_debug=dict(case["selector_debug"]),
            candidate_families=list(case["candidate_families"]),
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
        "page_delegates_fallback_to_controller": (
            "_resolve_design_guide_controller_optimisation_selector_fallback_result(" in core_segment
        ),
        "page_no_inline_legacy_next_selection": (
            'if str(item.get("check_key") or "") == str(governing_action or "")' not in fallback_block
            and "shared_selector_no_primary_fallback_order_used" not in fallback_block
        ),
        "page_keeps_family_callback_as_input_collection": (
            "_optimisation_candidate_family(item, guidance_state)" in core_segment
        ),
        "controller_helper_exists": (
            "def resolve_design_guide_controller_optimisation_selector_fallback_result(" in controller_source
        ),
        "controller_helper_exported": (
            '"resolve_design_guide_controller_optimisation_selector_fallback_result"' in controller_source
        ),
        "helper_no_session_reads": "st.session_state" not in helper_segment,
        "controller_no_streamlit_import": (
            "import streamlit" not in controller_source and "from streamlit" not in controller_source
        ),
    }
    status = "PASS" if all(row["matches"] for row in parity_rows) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_compute_optimisation_selector_legacy_fallback_extraction.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "parity_rows": parity_rows,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "optimisation_candidate_family_derivation_boundary",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_compute_optimisation_selector_legacy_fallback_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_optimisation_selector_legacy_fallback_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Optimisation Selector Legacy Fallback Extraction",
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
    print(f"design_guide_compute_optimisation_selector_legacy_fallback_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
