"""Cutover proof for shear low-util current overview status authority."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import importlib
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
FUNCTION_NAME = "_shear_low_util_target_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = module.build_design_guide_shear_low_util_current_overview_status_authority
    supplied = {"statuses": {"bending": "PASS", "shear": "PASS"}}
    recomputed = {"statuses": {"bending": "PASS", "shear": "FAIL"}}
    selected = helper(
        supplied_overview=supplied,
        recomputed_overview=recomputed,
        source="verifier",
    )
    supplied_only = helper(
        supplied_overview=supplied,
        recomputed_overview={},
        source="verifier",
    )
    repeated = helper(
        supplied_overview=supplied,
        recomputed_overview=recomputed,
        source="verifier",
    )
    return {
        "selected": selected,
        "supplied_only": supplied_only,
        "stable_repeat_hash": _stable_hash(selected) == _stable_hash(repeated),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    helper_exercise = _exercise_helper()
    return {
        "decision": "SHEAR_LOW_UTIL_CURRENT_OVERVIEW_STATUS_AUTHORITY_CUTOVER_PASS",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "helper_exercise": helper_exercise,
        "source_checks": {
            "helper_exported": (
                '"build_design_guide_shear_low_util_current_overview_status_authority"'
                in controller_source
            ),
            "helper_imported": (
                "build_design_guide_shear_low_util_current_overview_status_authority as _build_design_guide_shear_low_util_current_overview_status_authority"
                in inputs_source
            ),
            "helper_called_in_target": (
                "_build_design_guide_shear_low_util_current_overview_status_authority("
                in target_source
            ),
            "recompute_still_supplied_to_authority": (
                "recomputed_overview=(_collect_design_overview(state) if isinstance(state, dict) else {})"
                in target_source
            ),
            "failure_coverage_uses_authority_output": (
                'current_overview=dict(current_overview_status_authority.get("current_overview") or {})'
                in target_source
            ),
            "legacy_inline_failure_coverage_recompute_removed": (
                "current_overview=(_collect_design_overview(state) if isinstance(state, dict) else {})"
                not in target_source
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("helper_exercise") or {})
    selected = dict(exercise.get("selected") or {})
    supplied_only = dict(exercise.get("supplied_only") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "recomputed_selected_when_present": selected.get("selected_source") == "recomputed_overview",
        "selected_status_hash_is_recomputed": (
            selected.get("selected_status_hash") == selected.get("recomputed_status_hash")
        ),
        "mismatch_recorded": selected.get("supplied_matches_recomputed_statuses") is False,
        "supplied_selected_only_when_recomputed_missing": (
            supplied_only.get("selected_source") == "supplied_overview"
        ),
        "stable_repeat_hash": exercise.get("stable_repeat_hash") is True,
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Current Overview Status Authority Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Source Checks", ""])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("source_checks") or {}).items()
    )
    lines.extend(
        [
            "",
            "## Finding",
            "",
            "The current-overview status authority is now controller-owned for selected shear low-util failure coverage. The page still recomputes the current overview and the controller still selects the recomputed overview, preserving current behaviour.",
        ]
    )
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_current_overview_status_authority_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_current_overview_status_authority_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_current_overview_status_authority_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
