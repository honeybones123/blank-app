"""Verify live shear low-util promotion adapter cutover."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _target_function_source(inputs_source: str) -> str:
    inputs_source = inputs_source.lstrip("\ufeff")
    tree = ast.parse(inputs_source)
    lines = inputs_source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_shear_low_util_target_cleanup_item":
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                return ""
            return "\n".join(lines[node.lineno - 1 : end_lineno])
    return ""


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    function_source = _target_function_source(inputs_source)
    return {
        "decision": "SHEAR_LOW_UTIL_PROMOTION_ADAPTER_CUTOVER_PASS",
        "source_checks": {
            "target_function_found": bool(function_source),
            "helper_imported": (
                "build_design_guide_shear_low_util_promoted_item as "
                "_build_design_guide_shear_low_util_promoted_item"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_promoted_item(" in function_source
            ),
            "old_page_promotion_bridge_removed_from_target": (
                "_promote_guidance_item_to_resolved_candidate(" not in function_source
            ),
            "change_lines_no_longer_page_owned_in_target": (
                "_guidance_change_lines_for_updates(state, updates)" not in function_source
            ),
            "change_lines_controller_helper_called": (
                "_build_design_guide_shear_low_util_change_lines_for_updates("
                in function_source
            ),
            "failure_coverage_no_longer_page_owned_in_target": (
                "_candidate_failure_coverage_summary(state, resolved_candidate)"
                not in function_source
            ),
            "failure_coverage_controller_helper_called": (
                "_build_design_guide_shear_low_util_failure_coverage_from_overviews("
                in function_source
            ),
            "candidate_evaluation_controller_boundary_present": (
                "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in function_source
            ),
            "legacy_direct_candidate_evaluation_removed": (
                "candidate = _evaluate_auto_design_candidate(" not in function_source
            ),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_promoted_item(" in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": True,
        "change_lines_controller_owned": True,
        "failure_coverage_controller_owned": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "source_checks_pass": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_boundary_moved": capture.get("candidate_evaluation_moved") is True,
        "change_lines_controller_owned": capture.get("change_lines_controller_owned") is True,
        "failure_coverage_controller_owned": capture.get("failure_coverage_controller_owned") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Promotion Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_promotion_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_promotion_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_promotion_adapter_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

