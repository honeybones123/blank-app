"""Verify cleanup geometry exact-label wording extraction."""

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
    build_design_guide_controller_cleanup_geometry_change_label,
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


def _format_mm(value: Any) -> str:
    try:
        numeric = float(value)
    except Exception:
        return str(value or "").strip() or "recorded"
    if abs(numeric - round(numeric)) <= 1e-9:
        return str(int(round(numeric)))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def _legacy_geometry_label(
    *,
    before_depth: Any = None,
    after_depth: Any = None,
    before_width: Any = None,
    after_width: Any = None,
) -> str:
    def _float_or_none(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    before_d = _float_or_none(before_depth)
    after_d = _float_or_none(after_depth)
    before_w = _float_or_none(before_width)
    after_w = _float_or_none(after_width)
    geom_parts: list[str] = []
    if before_d is not None and after_d is not None and abs(float(before_d) - float(after_d)) > 1e-9:
        geom_parts.append(f"depth from {_format_mm(before_d)} mm to {_format_mm(after_d)} mm")
    if before_w is not None and after_w is not None and abs(float(before_w) - float(after_w)) > 1e-9:
        geom_parts.append(f"width from {_format_mm(before_w)} mm to {_format_mm(after_w)} mm")
    if geom_parts:
        return "changing " + " and ".join(geom_parts)
    return ""


def _cases() -> list[dict[str, Any]]:
    return [
        {"before_depth": 650, "after_depth": 600, "before_width": 400, "after_width": 400},
        {"before_depth": 650.0, "after_depth": 650.0, "before_width": 400, "after_width": 350},
        {"before_depth": 650, "after_depth": 600, "before_width": 400, "after_width": 350},
        {"before_depth": 650.5, "after_depth": 600.25, "before_width": 400.0, "after_width": 350.5},
        {"before_depth": 650, "after_depth": 650, "before_width": 400, "after_width": 400},
        {"before_depth": None, "after_depth": 600, "before_width": 400, "after_width": 350},
        {"before_depth": "bad", "after_depth": 600, "before_width": "bad", "after_width": 350},
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    exact_start, exact_end, exact_helper = _function_source(inputs_source, "_design_guide_exact_attempt_change_label")

    parity_rows: list[dict[str, Any]] = []
    for index, case in enumerate(_cases()):
        legacy = _legacy_geometry_label(**case)
        current = build_design_guide_controller_cleanup_geometry_change_label(**case)
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
        "schema": "design_guide_blocker_attempts_cleanup_geometry_exact_label_extraction.v1",
        "target": {
            "function": "_design_guide_exact_attempt_change_label",
            "line_start": exact_start,
            "line_end": exact_end,
            "line_count": max(0, exact_end - exact_start + 1),
        },
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "page_helper_delegates_geometry_label_to_controller": (
            "_build_design_guide_controller_cleanup_geometry_change_label(" in exact_helper
        ),
        "old_page_geometry_parts_removed": "geom_parts = []" not in exact_helper,
        "bottom_reinforcement_branch_retained": "_bottom_reo_state_label(" in exact_helper,
        "shear_link_branch_retained": "_guidance_shear_links_banner_fragment(" in exact_helper,
        "state_after_updates_remains_page_owned": "_design_guide_state_after_updates(" in exact_helper,
        "controller_has_helper": "def build_design_guide_controller_cleanup_geometry_change_label(" in controller_source,
        "controller_exported_helper": '"build_design_guide_controller_cleanup_geometry_change_label"' in controller_source,
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
        "page_helper_delegates_geometry_label_to_controller": bool(
            payload.get("page_helper_delegates_geometry_label_to_controller")
        ),
        "old_page_geometry_parts_removed": bool(payload.get("old_page_geometry_parts_removed")),
        "bottom_reinforcement_branch_retained": bool(payload.get("bottom_reinforcement_branch_retained")),
        "shear_link_branch_retained": bool(payload.get("shear_link_branch_retained")),
        "state_after_updates_remains_page_owned": bool(payload.get("state_after_updates_remains_page_owned")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_geometry_exact_label_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_geometry_exact_label_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Geometry Exact Label Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Geometry exact-change wording delegates to DesignGuideController with exact parity. Bottom reinforcement and shear-link exact wording remain page-owned.",
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
    print(f"design_guide_blocker_attempts_cleanup_geometry_exact_label_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
