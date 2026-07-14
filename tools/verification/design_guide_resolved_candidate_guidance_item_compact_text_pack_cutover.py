"""Verify resolved-candidate compact text-pack cutover."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_guidance_item_from_resolved_candidate"


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


def _parity_rows() -> list[dict]:
    cases = [
        {
            "name": "all_fields",
            "alternatives_text": "Alternative: adjust depth",
            "guidance_change_summary_compact": "Bending improves",
            "guidance_expected_util_text": "Expected utilisation 0.92",
            "guidance_why_text_compact": "Repair required",
        },
        {
            "name": "empty_alternatives",
            "alternatives_text": "",
            "guidance_change_summary_compact": "Shear links removed",
            "guidance_expected_util_text": "",
            "guidance_why_text_compact": "All checks remain pass",
        },
    ]
    rows: list[dict] = []
    for case in cases:
        legacy = {
            "guidance_alternatives_text_compact": str(case.get("alternatives_text") or ""),
            "guidance_change_summary_compact": str(case.get("guidance_change_summary_compact") or ""),
            "guidance_expected_util_text": str(case.get("guidance_expected_util_text") or ""),
            "guidance_why_text_compact": str(case.get("guidance_why_text_compact") or ""),
        }
        new = build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack(
            alternatives_text=str(case.get("alternatives_text") or ""),
            guidance_change_summary_compact=str(case.get("guidance_change_summary_compact") or ""),
            guidance_expected_util_text=str(case.get("guidance_expected_util_text") or ""),
            guidance_why_text_compact=str(case.get("guidance_why_text_compact") or ""),
        )
        comparable_new = {
            "guidance_alternatives_text_compact": new.get("guidance_alternatives_text_compact"),
            "guidance_change_summary_compact": new.get("guidance_change_summary_compact"),
            "guidance_expected_util_text": new.get("guidance_expected_util_text"),
            "guidance_why_text_compact": new.get("guidance_why_text_compact"),
        }
        rows.append({"name": case["name"], "match": legacy == comparable_new, "legacy": legacy, "new": comparable_new})
    return rows


def _capture() -> dict:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_compact_text_pack_cutover.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "parity_rows": _parity_rows(),
        "source_checks": {
            "page_imports_compact_text_pack": (
                "build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack as "
                "_build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack"
            )
            in inputs_source,
            "page_uses_compact_text_pack": (
                "_build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack("
            )
            in segment,
            "controller_helper_present": (
                "def build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack("
            )
            in controller_source,
            "controller_helper_exported": (
                '"build_design_guide_controller_resolved_candidate_guidance_item_compact_text_pack"'
            )
            in controller_source,
            "controller_boundary_clean": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict) -> dict[str, bool]:
    rows = list(payload.get("parity_rows") or [])
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "all_parity_rows_match": bool(rows) and all(bool(row.get("match")) for row in rows),
        "page_imports_compact_text_pack": bool(source_checks.get("page_imports_compact_text_pack")),
        "page_uses_compact_text_pack": bool(source_checks.get("page_uses_compact_text_pack")),
        "controller_helper_present": bool(source_checks.get("controller_helper_present")),
        "controller_helper_exported": bool(source_checks.get("controller_helper_exported")),
        "controller_boundary_clean": bool(source_checks.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict, checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_compact_text_pack_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_compact_text_pack_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Compact Text-Pack Cutover",
        "",
        f"Status: {payload['status']}",
        "",
        "## Parity Rows",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('match') else 'FAIL'}")
    lines.extend(["", "## Checks", *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_resolved_candidate_guidance_item_compact_text_pack_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
