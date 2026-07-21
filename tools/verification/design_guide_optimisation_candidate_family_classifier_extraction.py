"""Verify optimisation candidate family classifier extraction."""

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

APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
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


def _old_classifier(
    *,
    check_key: str | None,
    action_type: str | None,
    update_subfamilies: list[str],
    base_family: str | None,
) -> str:
    check = str(check_key or "").strip().lower()
    action = str(action_type or "").strip().lower()
    subs = {str(value).strip().lower() for value in update_subfamilies if str(value).strip()}
    base = str(base_family or "").strip().lower()
    if check in {"bending", "shear"}:
        return check
    if len(subs) >= 2:
        return "compound"
    if "bending" in subs or "bottom_reo" in subs:
        return "bending"
    if "shear" in subs:
        return "shear"
    if "geometry" in subs:
        return "geometry"
    if base in {"bending", "shear", "geometry", "compound"}:
        return base
    if action in {"reduce_bottom_reinforcement", "reduce_bar_spacing", "apply_bottom_recommendation"}:
        return "bending"
    if action in {"increase_link_spacing", "reduce_number_of_legs", "apply_shear_recommendation"}:
        return "shear"
    if action in {"tighten_geometry", "apply_geometry_recommendation", "increase_depth", "increase_width"}:
        return "geometry"
    return "other"


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_optimisation_candidate_family,
    )

    inputs_source = _read(APP_CONTRACT_BRIDGE)
    controller_source = _read(CONTROLLER)
    page_helper = _function_segment(inputs_source, "_optimisation_candidate_family")
    controller_helper = _function_segment(
        controller_source,
        "resolve_design_guide_controller_optimisation_candidate_family",
    )

    cases = [
        {"name": "check_key_bending", "check_key": "bending", "action_type": "", "subs": [], "base": "general"},
        {"name": "compound_subfamilies", "check_key": "", "action_type": "", "subs": ["geometry", "shear"], "base": ""},
        {"name": "bottom_reo_subfamily", "check_key": "", "action_type": "", "subs": ["bottom_reo"], "base": ""},
        {"name": "shear_subfamily", "check_key": "", "action_type": "", "subs": ["shear"], "base": ""},
        {"name": "geometry_subfamily", "check_key": "", "action_type": "", "subs": ["geometry"], "base": ""},
        {"name": "base_family", "check_key": "", "action_type": "", "subs": [], "base": "compound"},
        {
            "name": "bottom_action_type",
            "check_key": "",
            "action_type": "reduce_bottom_reinforcement",
            "subs": [],
            "base": "general",
        },
        {
            "name": "shear_action_type",
            "check_key": "",
            "action_type": "increase_link_spacing",
            "subs": [],
            "base": "general",
        },
        {
            "name": "geometry_action_type",
            "check_key": "",
            "action_type": "tighten_geometry",
            "subs": [],
            "base": "general",
        },
        {"name": "other", "check_key": "", "action_type": "noop", "subs": [], "base": "general"},
    ]
    parity_rows = []
    for case in cases:
        expected = _old_classifier(
            check_key=case["check_key"],
            action_type=case["action_type"],
            update_subfamilies=list(case["subs"]),
            base_family=case["base"],
        )
        actual = resolve_design_guide_controller_optimisation_candidate_family(
            check_key=case["check_key"],
            action_type=case["action_type"],
            update_subfamilies=list(case["subs"]),
            base_family=case["base"],
        )
        parity_rows.append(
            {
                "case": case["name"],
                "matches": expected == actual,
                "expected": expected,
                "actual": actual,
            }
        )

    source_checks = {
        "page_delegates_classifier": "_resolve_design_guide_controller_optimisation_candidate_family(" in page_helper,
        "page_keeps_update_resolution_as_input_collection": (
            "_guidance_action_updates(" in page_helper and "_compound_subfamilies_from_updates(" in page_helper
        ),
        "page_no_inline_classifier_decision_tree": (
            'if len(update_subfamilies) >= 2:' not in page_helper
            and 'if "shear" in update_subfamilies:' not in page_helper
            and 'if action_type in {"increase_link_spacing"' not in page_helper
        ),
        "controller_helper_exists": (
            "def resolve_design_guide_controller_optimisation_candidate_family(" in controller_source
        ),
        "controller_helper_exported": (
            '"resolve_design_guide_controller_optimisation_candidate_family"' in controller_source
        ),
        "helper_no_session_reads": "st.session_state" not in controller_helper,
        "controller_no_streamlit_import": (
            "import streamlit" not in controller_source and "from streamlit" not in controller_source
        ),
    }
    status = "PASS" if all(row["matches"] for row in parity_rows) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_optimisation_candidate_family_classifier_extraction.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "parity_rows": parity_rows,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "compute_guidance_core_tail_inventory_refresh",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_optimisation_candidate_family_classifier_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_optimisation_candidate_family_classifier_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Optimisation Candidate Family Classifier Extraction",
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
    print(f"design_guide_optimisation_candidate_family_classifier_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
