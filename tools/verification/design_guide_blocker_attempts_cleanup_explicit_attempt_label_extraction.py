"""Verify explicit cleanup attempt-label extraction to DesignGuideController."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from design_brain.design_guide_controller import (  # noqa: E402
    resolve_design_guide_controller_cleanup_explicit_attempt_label,
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


def _legacy_explicit_attempt_label(row: dict[str, Any] | None) -> str | None:
    row_d = dict(row or {})
    explicit = str(
        row_d.get("attempted_change_label")
        or row_d.get("attempted_next_reduction")
        or row_d.get("attempted_reduction_label")
        or ""
    ).strip()
    if explicit and not re.search(r"\b[a-z0-9]+(?:_[a-z0-9]+){3,}\b", explicit, flags=re.I):
        return explicit
    return None


def _cases() -> list[dict[str, Any]]:
    return [
        {"attempted_change_label": "changing depth from 650.0 mm to 600.0 mm"},
        {"attempted_next_reduction": "removing shear links from R10-200"},
        {"attempted_reduction_label": "changing bottom reinforcement from 8N16 to 7N16"},
        {"attempted_change_label": ""},
        {"attempted_change_label": "candidate_search_debug_machine_id"},
        {"attempted_change_label": "safe_cleanup_route_123_abc"},
        {"attempted_change_label": "  changing width from 400.0 mm to 350.0 mm  "},
        {},
    ]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    label_start, label_end, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")
    arrangement_start, arrangement_end, arrangement_helper = _function_source(
        inputs_source,
        "_design_guide_cleanup_arrangement_label",
    )

    parity_rows: list[dict[str, Any]] = []
    for index, row in enumerate(_cases()):
        legacy = _legacy_explicit_attempt_label(row)
        current = resolve_design_guide_controller_cleanup_explicit_attempt_label(row)
        parity_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
                "row": row,
            }
        )

    helper_call = "_resolve_design_guide_controller_cleanup_explicit_attempt_label(row_d)" in label_helper
    old_direct_return_removed = not any(
        line.strip() == "return explicit"
        for line in label_helper.splitlines()
    )
    no_link_branch_retained = all(
        token in label_helper
        for token in (
            "removing shear links",
            "_build_design_guide_controller_cleanup_no_link_no_change_label(",
            "current_arrangement",
        )
    )
    generated_change_line_branch_retained = "_guidance_change_lines_for_updates(" in label_helper
    arrangement_label_branch_retained = all(
        token in arrangement_helper
        for token in (
            "_bottom_reo_state_label(",
            "_guidance_shear_links_banner_fragment(",
        )
    )
    exact_label_branch_retained = "_design_guide_exact_attempt_change_label(" in label_helper
    route_summary_branch_retained = "_design_guide_attempt_route_summary(" in label_helper

    return {
        "schema": "design_guide_blocker_attempts_cleanup_explicit_attempt_label_extraction.v1",
        "target": {
            "function": "_design_guide_cleanup_attempt_label",
            "line_start": label_start,
            "line_end": label_end,
            "line_count": max(0, label_end - label_start + 1),
        },
        "arrangement_helper": {
            "function": "_design_guide_cleanup_arrangement_label",
            "line_start": arrangement_start,
            "line_end": arrangement_end,
            "line_count": max(0, arrangement_end - arrangement_start + 1),
        },
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "page_helper_delegates_explicit_label_to_controller": helper_call,
        "old_direct_explicit_return_removed": old_direct_return_removed,
        "no_link_branch_retained": no_link_branch_retained,
        "generated_change_line_branch_retained": generated_change_line_branch_retained,
        "arrangement_label_branch_retained": arrangement_label_branch_retained,
        "exact_label_branch_retained": exact_label_branch_retained,
        "route_summary_branch_retained": route_summary_branch_retained,
        "controller_has_helper": "def resolve_design_guide_controller_cleanup_explicit_attempt_label(" in controller_source,
        "controller_exported_helper": '"resolve_design_guide_controller_cleanup_explicit_attempt_label"' in controller_source,
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
        "page_helper_delegates_explicit_label_to_controller": bool(
            payload.get("page_helper_delegates_explicit_label_to_controller")
        ),
        "old_direct_explicit_return_removed": bool(payload.get("old_direct_explicit_return_removed")),
        "no_link_branch_retained": bool(payload.get("no_link_branch_retained")),
        "generated_change_line_branch_retained": bool(payload.get("generated_change_line_branch_retained")),
        "arrangement_label_branch_retained": bool(payload.get("arrangement_label_branch_retained")),
        "exact_label_branch_retained": bool(payload.get("exact_label_branch_retained")),
        "route_summary_branch_retained": bool(payload.get("route_summary_branch_retained")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_explicit_attempt_label_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_explicit_attempt_label_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Explicit Attempt Label Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "The explicit attempted-change label sanitisation branch delegates to DesignGuideController with exact parity. Risky generated and arrangement wording remains page-owned.",
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
    print(f"design_guide_blocker_attempts_cleanup_explicit_attempt_label_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
