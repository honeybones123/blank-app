"""Verify optimisation selector default debug context extraction."""

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


def _old_default_context(governing_action: str | None) -> dict[str, Any]:
    return {
        "optimisation_selector_governing_action": str(governing_action or "other"),
        "optimisation_selector_family_bias_applied": False,
        "optimisation_selector_candidate_counts_by_family": {},
        "optimisation_selector_winning_family": None,
        "optimisation_selector_used_geometry_fallback": False,
        "optimisation_selector_fallback_reason": None,
        "optimisation_selector_candidate_reaches_target_band": False,
        "optimisation_selector_candidate_all_key_pass": False,
        "primary_optimisation_selection_owner": "controller_fallback",
    }


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_optimisation_selector_default_debug_context,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    core_segment = _function_segment(inputs_source, "_compute_design_guidance_items_core")
    helper_segment = _function_segment(
        controller_source,
        "build_design_guide_controller_optimisation_selector_default_debug_context",
    )
    cases = ["bending", "shear", "", None]
    parity_rows = []
    for case in cases:
        expected = _old_default_context(case)
        actual = build_design_guide_controller_optimisation_selector_default_debug_context(
            governing_action=case,
        )
        parity_rows.append(
            {
                "case": str(case),
                "matches": _stable(expected) == _stable(actual),
                "expected": expected,
                "actual": actual,
            }
        )

    source_checks = {
        "page_delegates_default_context": (
            "_build_design_guide_controller_optimisation_selector_default_debug_context(" in core_segment
        ),
        "page_no_inline_default_context_rows": (
            'debug_sink.setdefault("optimisation_selector_governing_action"' not in core_segment
            and 'debug_sink.setdefault("primary_optimisation_selection_owner"' not in core_segment
        ),
        "page_still_owns_debug_sink_write": "debug_sink.setdefault(key, value)" in core_segment,
        "controller_helper_exists": (
            "def build_design_guide_controller_optimisation_selector_default_debug_context(" in controller_source
        ),
        "controller_helper_exported": (
            '"build_design_guide_controller_optimisation_selector_default_debug_context"' in controller_source
        ),
        "helper_no_session_reads": "st.session_state" not in helper_segment,
        "controller_no_streamlit_import": (
            "import streamlit" not in controller_source and "from streamlit" not in controller_source
        ),
    }
    status = "PASS" if all(row["matches"] for row in parity_rows) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_compute_optimisation_selector_default_debug_context_extraction.v1",
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_optimisation_selector_default_debug_context_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_optimisation_selector_default_debug_context_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Optimisation Selector Default Debug Context Extraction",
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
    print(f"design_guide_compute_optimisation_selector_default_debug_context_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
