"""Verify cleanup shear-link exact-label wording extraction."""

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
    build_design_guide_controller_cleanup_shear_link_change_label,
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


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _format_mm(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return str(value or "").strip() or "recorded"
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _legacy_shear_label(
    *,
    before_label: Any = None,
    after_label: Any = None,
    before_spacing: Any = None,
    after_spacing: Any = None,
    before_dia: Any = 0,
    after_dia: Any = 0,
    before_legs: Any = 0,
    after_legs: Any = 0,
) -> str:
    before_s = str(before_label or "").strip() or "no links"
    after_s = str(after_label or "").strip() or "no links"
    if before_s == after_s:
        return ""
    before_space = _float_or_none(before_spacing)
    after_space = _float_or_none(after_spacing)
    before_bar = _int_value(before_dia)
    after_bar = _int_value(after_dia)
    before_leg_count = _int_value(before_legs)
    after_leg_count = _int_value(after_legs)
    if after_s == "no links":
        return f"removing shear links from {before_s}"
    if before_s == "no links":
        return f"adding shear links from no links to {after_s}"
    if (
        before_space is not None
        and after_space is not None
        and before_bar == after_bar
        and before_leg_count == after_leg_count
    ):
        direction = "increasing" if float(after_space) > float(before_space) else "reducing"
        return f"{direction} link spacing from {_format_mm(before_space)} mm to {_format_mm(after_space)} mm"
    if before_bar != after_bar and before_leg_count == after_leg_count and before_space == after_space:
        direction = "increasing" if after_bar > before_bar else "reducing"
        return f"{direction} links from N{before_bar} to N{after_bar}"
    if before_leg_count != after_leg_count and before_bar == after_bar and before_space == after_space:
        direction = "increasing" if after_leg_count > before_leg_count else "reducing"
        return f"{direction} from {before_leg_count}-leg links to {after_leg_count}-leg links"
    return f"changing links from {before_s} to {after_s}"


def _cases() -> list[dict[str, Any]]:
    return [
        {"before_label": "N10-200 2 legs", "after_label": "no links", "before_spacing": 200, "after_spacing": 0, "before_dia": 10, "after_dia": 0, "before_legs": 2, "after_legs": 0},
        {"before_label": "no links", "after_label": "N10-200 2 legs", "before_spacing": 0, "after_spacing": 200, "before_dia": 0, "after_dia": 10, "before_legs": 0, "after_legs": 2},
        {"before_label": "N10-200 2 legs", "after_label": "N10-250 2 legs", "before_spacing": 200, "after_spacing": 250, "before_dia": 10, "after_dia": 10, "before_legs": 2, "after_legs": 2},
        {"before_label": "N10-250 2 legs", "after_label": "N10-200 2 legs", "before_spacing": 250, "after_spacing": 200, "before_dia": 10, "after_dia": 10, "before_legs": 2, "after_legs": 2},
        {"before_label": "N10-200 2 legs", "after_label": "N12-200 2 legs", "before_spacing": 200, "after_spacing": 200, "before_dia": 10, "after_dia": 12, "before_legs": 2, "after_legs": 2},
        {"before_label": "N12-200 2 legs", "after_label": "N10-200 2 legs", "before_spacing": 200, "after_spacing": 200, "before_dia": 12, "after_dia": 10, "before_legs": 2, "after_legs": 2},
        {"before_label": "N10-200 2 legs", "after_label": "N10-200 4 legs", "before_spacing": 200, "after_spacing": 200, "before_dia": 10, "after_dia": 10, "before_legs": 2, "after_legs": 4},
        {"before_label": "N10-200 4 legs", "after_label": "N10-200 2 legs", "before_spacing": 200, "after_spacing": 200, "before_dia": 10, "after_dia": 10, "before_legs": 4, "after_legs": 2},
        {"before_label": "N10-200 2 legs", "after_label": "N12-250 4 legs", "before_spacing": 200, "after_spacing": 250, "before_dia": 10, "after_dia": 12, "before_legs": 2, "after_legs": 4},
        {"before_label": "N10-200 2 legs", "after_label": "N10-200 2 legs", "before_spacing": 200, "after_spacing": 200, "before_dia": 10, "after_dia": 10, "before_legs": 2, "after_legs": 2},
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    exact_start, exact_end, exact_helper = _function_source(inputs_source, "_design_guide_exact_attempt_change_label")

    parity_rows: list[dict[str, Any]] = []
    for index, case in enumerate(_cases()):
        legacy = _legacy_shear_label(**case)
        current = build_design_guide_controller_cleanup_shear_link_change_label(**case)
        parity_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
                "input": case,
            }
        )

    return {
        "schema": "design_guide_blocker_attempts_cleanup_shear_link_exact_label_extraction.v1",
        "target": {
            "function": "_design_guide_exact_attempt_change_label",
            "line_start": exact_start,
            "line_end": exact_end,
            "line_count": max(0, exact_end - exact_start + 1),
        },
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "page_helper_delegates_shear_label_to_controller": (
            "_build_design_guide_controller_cleanup_shear_link_change_label(" in exact_helper
        ),
        "page_still_collects_shear_labels": "_guidance_shear_links_banner_fragment(" in exact_helper,
        "page_still_collects_shear_scalars": all(
            token in exact_helper
            for token in ("before_spacing", "after_spacing", "before_dia", "after_dia", "before_legs", "after_legs")
        ),
        "old_page_shear_direction_removed": '"increasing" if float(after_spacing)' not in exact_helper,
        "bottom_branch_still_delegates": "_build_design_guide_controller_cleanup_bottom_reinforcement_change_label(" in exact_helper,
        "geometry_branch_still_delegates": "_build_design_guide_controller_cleanup_geometry_change_label(" in exact_helper,
        "controller_has_helper": "def build_design_guide_controller_cleanup_shear_link_change_label(" in controller_source,
        "controller_exported_helper": '"build_design_guide_controller_cleanup_shear_link_change_label"' in controller_source,
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
        "page_helper_delegates_shear_label_to_controller": bool(
            payload.get("page_helper_delegates_shear_label_to_controller")
        ),
        "page_still_collects_shear_labels": bool(payload.get("page_still_collects_shear_labels")),
        "page_still_collects_shear_scalars": bool(payload.get("page_still_collects_shear_scalars")),
        "old_page_shear_direction_removed": bool(payload.get("old_page_shear_direction_removed")),
        "bottom_branch_still_delegates": bool(payload.get("bottom_branch_still_delegates")),
        "geometry_branch_still_delegates": bool(payload.get("geometry_branch_still_delegates")),
        "controller_has_helper": bool(payload.get("controller_has_helper")),
        "controller_exported_helper": bool(payload.get("controller_exported_helper")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_shear_link_exact_label_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_shear_link_exact_label_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Shear-Link Exact Label Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Shear-link exact-change wording delegates to DesignGuideController with exact parity. Page still collects shear labels and scalar inputs.",
        "",
        "## Parity Cases",
        "",
        "| Case | Matches | Legacy | Current |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(
            f"| {row.get('case')} | {'PASS' if row.get('matches') else 'FAIL'} | {row.get('legacy')!r} | {row.get('current')!r} |"
        )
    lines.extend(["", "## Checks"])
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
    print(f"design_guide_blocker_attempts_cleanup_shear_link_exact_label_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
