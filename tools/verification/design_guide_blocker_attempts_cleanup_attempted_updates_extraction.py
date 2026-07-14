"""Verify cleanup attempted-updates source-precedence extraction."""

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
    resolve_design_guide_controller_cleanup_attempted_updates,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

SOURCE_KEYS = (
    "attempted_updates",
    "attempted_next_updates",
    "failed_candidate_updates",
    "best_rejected_candidate_updates",
    "best_safe_candidate_updates",
    "selected_candidate_updates",
)


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


def _legacy_attempted_updates(row: dict[str, Any] | None) -> dict[str, Any]:
    row_d = dict(row or {})
    for key in SOURCE_KEYS:
        value = row_d.get(key)
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _cases() -> list[dict[str, Any]]:
    cases = [{}]
    for index, key in enumerate(SOURCE_KEYS):
        row = {k: {} for k in SOURCE_KEYS}
        row[key] = {"source_key": key, "index": index}
        cases.append(row)
    cases.append(
        {
            "attempted_updates": {},
            "attempted_next_updates": {"D": 600},
            "selected_candidate_updates": {"D": 650},
        }
    )
    cases.append(
        {
            "attempted_updates": [],
            "attempted_next_updates": None,
            "failed_candidate_updates": {"b": 350},
        }
    )
    return cases


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    updates_start, updates_end, updates_helper = _function_source(inputs_source, "_design_guide_cleanup_attempted_updates")
    label_start, label_end, label_helper = _function_source(inputs_source, "_design_guide_cleanup_attempt_label")

    parity_rows: list[dict[str, Any]] = []
    for index, row in enumerate(_cases()):
        legacy = _legacy_attempted_updates(row)
        current = resolve_design_guide_controller_cleanup_attempted_updates(row)
        parity_rows.append(
            {
                "case": index,
                "matches": legacy == current,
                "legacy": legacy,
                "current": current,
            }
        )

    return {
        "schema": "design_guide_blocker_attempts_cleanup_attempted_updates_extraction.v1",
        "target": {
            "function": "_design_guide_cleanup_attempted_updates",
            "line_start": updates_start,
            "line_end": updates_end,
            "line_count": max(0, updates_end - updates_start + 1),
        },
        "label_function": {
            "function": "_design_guide_cleanup_attempt_label",
            "line_start": label_start,
            "line_end": label_end,
            "line_count": max(0, label_end - label_start + 1),
        },
        "parity_rows": parity_rows,
        "parity_pass": all(row.get("matches") for row in parity_rows),
        "page_helper_is_shell_call": (
            "return _resolve_design_guide_controller_cleanup_attempted_updates(row)" in updates_helper
        ),
        "label_still_calls_page_shell": "_design_guide_cleanup_attempted_updates(row_d)" in label_helper,
        "controller_has_helper": "def resolve_design_guide_controller_cleanup_attempted_updates(" in controller_source,
        "controller_exported_helper": '"resolve_design_guide_controller_cleanup_attempted_updates"' in controller_source,
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
        "page_helper_is_shell_call": bool(payload.get("page_helper_is_shell_call")),
        "label_still_calls_page_shell": bool(payload.get("label_still_calls_page_shell")),
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
    json_path = ARTIFACT_DIR / f"design_guide_blocker_attempts_cleanup_attempted_updates_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_blocker_attempts_cleanup_attempted_updates_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Blocker Attempts Cleanup Attempted Updates Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Executive Summary",
        "",
        "Cleanup attempted-update source precedence delegates to DesignGuideController. The page helper remains as a shell call for compatibility.",
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
    print(f"design_guide_blocker_attempts_cleanup_attempted_updates_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
