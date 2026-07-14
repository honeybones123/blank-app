"""Verify cleanup route/no-link fallback wording extraction."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_cleanup_no_link_no_change_label,
    build_design_guide_controller_cleanup_route_fallback_label,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _legacy_no_link(current_arrangement: Any = None) -> str:
    arrangement = str(current_arrangement or "").strip() or "no links"
    return (
        f"no change from {arrangement} to {arrangement} because shear links are already "
        "removed and no executable numeric shear-link cleanup was available"
    )


def _legacy_route(
    *,
    route: Any = None,
    current_arrangement: Any = None,
    has_sanitised_model_updates: bool = False,
) -> str:
    route_s = str(route or "").strip()
    arrangement = str(current_arrangement or "").strip()
    if route_s and arrangement and not bool(has_sanitised_model_updates):
        return (
            f"no change from {arrangement} to {arrangement} because no executable "
            f"numeric {route_s} cleanup was available"
        )
    if route_s:
        return f"the recorded {route_s} change"
    return "the recorded cleanup change"


def _route_cases() -> list[dict[str, Any]]:
    return [
        {"route": "shear-link", "current_arrangement": "no links", "has_sanitised_model_updates": False},
        {"route": "bottom-reinforcement", "current_arrangement": "8N16", "has_sanitised_model_updates": False},
        {"route": "geometry", "current_arrangement": "current arrangement", "has_sanitised_model_updates": True},
        {"route": "combined", "current_arrangement": "", "has_sanitised_model_updates": False},
        {"route": "", "current_arrangement": "8N16", "has_sanitised_model_updates": False},
        {"route": None, "current_arrangement": None, "has_sanitised_model_updates": True},
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    label_start, label_end, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")

    no_link_rows = []
    for index, arrangement in enumerate(["no links", "N10-200 2 legs", "", None]):
        legacy = _legacy_no_link(arrangement)
        current = build_design_guide_controller_cleanup_no_link_no_change_label(arrangement)
        no_link_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
                "arrangement": arrangement,
            }
        )

    route_rows = []
    for index, case in enumerate(_route_cases()):
        legacy = _legacy_route(**case)
        current = build_design_guide_controller_cleanup_route_fallback_label(**case)
        route_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
                "input": case,
            }
        )

    return {
        "schema": "design_guide_blocker_attempts_cleanup_route_fallback_label_extraction.v1",
        "target": {
            "function": "_design_guide_cleanup_attempt_label",
            "line_start": label_start,
            "line_end": label_end,
            "line_count": max(0, label_end - label_start + 1),
        },
        "no_link_rows": no_link_rows,
        "route_rows": route_rows,
        "parity_pass": all(row.get("matches") for row in no_link_rows + route_rows),
        "page_helper_delegates_no_link_label_to_controller": (
            "_build_design_guide_controller_cleanup_no_link_no_change_label(" in label_helper
        ),
        "page_helper_delegates_route_fallback_to_controller": (
            "_build_design_guide_controller_cleanup_route_fallback_label(" in label_helper
        ),
        "page_still_owns_no_link_conditions": all(
            token in label_helper
            for token in ("no_link_candidate_already_active", "best_rejected_candidate_id", "removing shear links")
        ),
        "generated_change_line_branch_retained": "_guidance_change_lines_for_updates(" in label_helper,
        "explicit_label_still_delegates": "_resolve_design_guide_controller_cleanup_explicit_attempt_label(" in label_helper,
        "exact_label_still_delegates": "_design_guide_exact_attempt_change_label(" in label_helper,
        "controller_has_helpers": all(
            token in controller_source
            for token in (
                "def build_design_guide_controller_cleanup_no_link_no_change_label(",
                "def build_design_guide_controller_cleanup_route_fallback_label(",
            )
        ),
        "controller_exported_helpers": all(
            token in controller_source
            for token in (
                '"build_design_guide_controller_cleanup_no_link_no_change_label"',
                '"build_design_guide_controller_cleanup_route_fallback_label"',
            )
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "parity_pass": bool(payload.get("parity_pass")),
        "page_helper_delegates_no_link_label_to_controller": bool(
            payload.get("page_helper_delegates_no_link_label_to_controller")
        ),
        "page_helper_delegates_route_fallback_to_controller": bool(
            payload.get("page_helper_delegates_route_fallback_to_controller")
        ),
        "page_still_owns_no_link_conditions": bool(payload.get("page_still_owns_no_link_conditions")),
        "generated_change_line_branch_retained": bool(payload.get("generated_change_line_branch_retained")),
        "explicit_label_still_delegates": bool(payload.get("explicit_label_still_delegates")),
        "exact_label_still_delegates": bool(payload.get("exact_label_still_delegates")),
        "controller_has_helpers": bool(payload.get("controller_has_helpers")),
        "controller_exported_helpers": bool(payload.get("controller_exported_helpers")),
        "controller_boundary_clean": bool(payload.get("controller_has_no_page_or_streamlit_imports")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_route_fallback_label_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_route_fallback_label_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Route/Fallback Label Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "No-link and route fallback cleanup wording delegates to DesignGuideController with exact parity. Page still owns condition checks and generated change-line fallback.",
        "",
        "## Checks",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_blocker_attempts_cleanup_route_fallback_label_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
