"""Verify serviceability exact-blocker projection extraction from inputs_page.py."""

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


def _expected_old_projection(
    *,
    primary_check: str,
    primary_item: dict[str, Any],
    existing_evidence: dict[str, Any],
    failed_row: dict[str, Any],
) -> dict[str, Any]:
    check = str(primary_check or "").strip().lower()
    evidence = dict(existing_evidence or {})
    attempted_updates = (
        {
            "bot1_count": "increase bottom bar count trial",
            "db_bot_1": "increase bottom bar diameter trial",
            "D": "increase section depth trial",
            "b": "increase section width trial",
        }
        if check == "crack"
        else {
            "D": "increase section depth trial",
            "b": "increase section width trial",
            "sustained_load": "reduce sustained load advisory trial",
        }
    )
    reason = (
        "No one-click crack-control arrangement from the practical bar/count/diameter and "
        "section geometry trials resolved the crack limit while preserving bending, shear, "
        "deflection, spacing, ductility, cover, and detailing checks."
        if check == "crack"
        else
        "No one-click deflection arrangement from the practical depth, width, and sustained-load "
        "trials resolved the deflection limit while preserving bending, shear, crack control, "
        "spacing, ductility, cover, and detailing checks."
    )
    evidence.update(
        {
            "candidate_search_exhaustive": True,
            "search_scope": f"serviceability_{check}_active_failure_ladder",
            "total_candidates_considered": max(
                int(evidence.get("total_candidates_considered") or 0),
                len(attempted_updates),
            ),
            "safe_executor_backed_candidates_count": 0,
            "target_band_candidate_count": 0,
            "active_under_capacity_blocker": True,
            "active_under_capacity_blocker_family": check,
            "active_under_capacity_blocker_reason": reason,
            "outside_target_band_allowed": False,
            "outside_target_band_allowed_reason": reason,
            "outside_target_band_allowed_category": f"{check}_would_fail",
            "attempted_candidate_id": f"{check}_serviceability_practical_ladder_exhausted",
            "attempted_updates": dict(attempted_updates),
            "failed_check_name": str(failed_row.get("title") or f"{check} limit"),
            "failed_check_status": str(failed_row.get("status") or "FAIL"),
            "failed_check_util": primary_item.get("util"),
            "failed_check_demand": str(
                failed_row.get("calculated")
                or failed_row.get("value")
                or failed_row.get("action")
                or f"{check} demand"
            ),
            "failed_check_capacity_or_limit": str(
                failed_row.get("requirement")
                or failed_row.get("limit")
                or f"{check} limit"
            ),
            "one_click_target_reaching_candidate_exists": False,
        }
    )
    display_truth = {
        "display_truth_source": "published_summary",
        "displayed_util": primary_item.get("util"),
        "displayed_status": "FAIL",
        "target_low": evidence.get("target_low"),
        "target_high": evidence.get("target_high"),
        "displayed_within_target_band": False,
        "source_summary_util": primary_item.get("util"),
        "source_candidate_util": None,
        "source_post_commit_util": None,
    }
    return {
        "applied": True,
        "primary_check": check,
        "existing_evidence": dict(evidence),
        "display_truth": dict(display_truth),
        "item_projection": {
            "display_truth": dict(display_truth),
            "display_truth_source": "published_summary",
            "displayed_util": primary_item.get("util"),
            "displayed_status": "FAIL",
            "source_summary_util": primary_item.get("util"),
            "source_candidate_util": None,
        },
    }


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_compute_serviceability_exact_blocker_projection,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    wrapper_segment = _function_segment(inputs_source, "_compute_design_guidance_items")
    helper_segment = _function_segment(
        controller_source,
        "build_design_guide_controller_compute_serviceability_exact_blocker_projection",
    )
    cases = [
        {
            "name": "crack_failed_row",
            "primary_check": "crack",
            "primary_item": {"util": 1.23},
            "existing_evidence": {"target_low": 0.85, "target_high": 1.0, "total_candidates_considered": 1},
            "failed_row": {
                "title": "Crack control",
                "status": "FAIL",
                "calculated": "w* = 0.41 mm",
                "requirement": "w* <= 0.30 mm",
            },
        },
        {
            "name": "deflection_defaults",
            "primary_check": "deflection",
            "primary_item": {"util": 1.04},
            "existing_evidence": {"target_low": 0.85, "target_high": 1.0, "total_candidates_considered": 8},
            "failed_row": {},
        },
    ]
    parity_rows = []
    for case in cases:
        expected = _expected_old_projection(
            primary_check=str(case["primary_check"]),
            primary_item=dict(case["primary_item"]),
            existing_evidence=dict(case["existing_evidence"]),
            failed_row=dict(case["failed_row"]),
        )
        actual = build_design_guide_controller_compute_serviceability_exact_blocker_projection(
            primary_check=str(case["primary_check"]),
            primary_item=dict(case["primary_item"]),
            existing_evidence=dict(case["existing_evidence"]),
            failed_row=dict(case["failed_row"]),
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
        "page_delegates_to_controller": "_build_design_guide_controller_compute_serviceability_exact_blocker_projection(" in wrapper_segment,
        "page_no_longer_embeds_crack_reason": "No one-click crack-control arrangement from the practical bar/count/diameter" not in wrapper_segment,
        "page_no_longer_embeds_deflection_reason": "No one-click deflection arrangement from the practical depth" not in wrapper_segment,
        "page_no_longer_builds_attempted_updates": "_attempted_updates_for_evidence =" not in wrapper_segment,
        "controller_helper_exists": "def build_design_guide_controller_compute_serviceability_exact_blocker_projection(" in controller_source,
        "controller_helper_exported": '"build_design_guide_controller_compute_serviceability_exact_blocker_projection"' in controller_source,
        "controller_no_streamlit_import": "import streamlit" not in controller_source and "from streamlit" not in controller_source,
    }
    status = "PASS" if all(row["matches"] for row in parity_rows) and all(source_checks.values()) else "FAIL"
    return {
        "schema": "design_guide_compute_serviceability_blocker_projection_extraction.v1",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ"),
        "status": status,
        "parity_rows": parity_rows,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "post_active_shear_cleanup_blocked_item_projection",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_compute_serviceability_blocker_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_serviceability_blocker_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Design Guide Compute Serviceability Blocker Projection Extraction",
        "",
        "## Executive Summary",
        str(payload["status"]),
        "",
        "## Parity",
        *[
            f"- {row['case']}: {'PASS' if row['matches'] else 'FAIL'}"
            for row in payload["parity_rows"]
        ],
        "",
        "## Source Checks",
        *[
            f"- {key}: {value}"
            for key, value in payload["source_checks"].items()
        ],
        "",
        "## Next Safe Target",
        str(payload["next_safe_target"]),
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = _write(payload)
    print(f"design_guide_compute_serviceability_blocker_projection_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
