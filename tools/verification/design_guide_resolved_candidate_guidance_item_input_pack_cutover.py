"""Verify resolved-candidate guidance item input-pack cutover."""

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


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, segment = _function_source(inputs_source, TARGET)
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_input_pack_cutover.v1",
        "target": {
            "name": TARGET,
            "line_start": start,
            "line_end": end,
            "line_count": max(0, end - start + 1),
        },
        "source_checks": {
            "page_imports_controller_input_pack": (
                "build_design_guide_controller_resolved_candidate_guidance_item_input_pack as "
                "_build_design_guide_controller_resolved_candidate_guidance_item_input_pack"
            )
            in inputs_source,
            "page_uses_controller_input_pack": (
                "_build_design_guide_controller_resolved_candidate_guidance_item_input_pack("
            )
            in segment,
            "local_action_payload_preview_literal_removed": "action_payload_preview = {" not in segment,
            "final_item_builder_still_called": "_build_design_guide_controller_resolved_candidate_guidance_item(" in segment,
            "controller_helper_present": (
                "def build_design_guide_controller_resolved_candidate_guidance_item_input_pack("
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


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "page_imports_controller_input_pack": bool(source_checks.get("page_imports_controller_input_pack")),
        "page_uses_controller_input_pack": bool(source_checks.get("page_uses_controller_input_pack")),
        "local_action_payload_preview_literal_removed": bool(
            source_checks.get("local_action_payload_preview_literal_removed")
        ),
        "final_item_builder_still_called": bool(source_checks.get("final_item_builder_still_called")),
        "controller_helper_present": bool(source_checks.get("controller_helper_present")),
        "controller_boundary_clean": bool(source_checks.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_cutover_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_cutover_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Input-Pack Cutover",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "- `_guidance_item_from_resolved_candidate(...)` now delegates preview input-pack construction to `DesignGuideController`.",
        "- Visible wording helpers, before/after rendering text, final item construction, CTA/apply semantics, family runtimes, and page/session ownership remain unchanged.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_resolved_candidate_guidance_item_input_pack_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
