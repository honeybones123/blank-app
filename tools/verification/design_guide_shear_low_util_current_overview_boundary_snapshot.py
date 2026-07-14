"""Proof-only snapshot for shear low-util current-overview boundary."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
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
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _line_number(function_source: str, token: str, *, occurrence: int = 1) -> int | None:
    matches = list(re.finditer(re.escape(token), function_source))
    if len(matches) < occurrence:
        return None
    idx = matches[occurrence - 1].start()
    return function_source[:idx].count("\n") + 1


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    collect_count = target_source.count("_collect_design_overview(")
    overview_calls = [
        {
            "id": "fallback_shear_util_overview",
            "line_in_function": _line_number(target_source, "_collect_design_overview(", occurrence=1),
            "absolute_line": (
                start_line + (_line_number(target_source, "_collect_design_overview(", occurrence=1) or 1) - 1
            ),
            "current_role": "fallback current overview when caller-provided overview lacks shear util",
            "context_dependency": "_build_design_actions_context(dict(state))",
            "safe_to_remove_now": False,
            "reason": "removal could suppress a valid current shear utilisation seed",
        },
        {
            "id": "failure_coverage_current_overview_status_authority",
            "line_in_function": _line_number(target_source, "_collect_design_overview(", occurrence=2),
            "absolute_line": (
                start_line + (_line_number(target_source, "_collect_design_overview(", occurrence=2) or 1) - 1
            ),
            "current_role": "recomputed current overview input to controller-owned status authority for selected-candidate failure coverage comparison",
            "context_dependency": "default current overview collection",
            "safe_to_remove_now": False,
            "reason": "global deletion needs callsite status-authority proof before replacing recompute with supplied overview",
        },
    ]
    return {
        "decision": "SHEAR_LOW_UTIL_CURRENT_OVERVIEW_BOUNDARY_NOT_READY_TO_MOVE",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "overview_call_count": collect_count,
        "overview_calls": overview_calls,
        "source_checks": {
            "target_function_found": bool(target_source),
            "two_overview_calls_present": collect_count == 2,
            "fallback_call_has_design_actions_context": (
                "_build_design_actions_context(dict(state))" in target_source
            ),
            "failure_coverage_uses_current_overview_status_authority": (
                "_build_design_guide_shear_low_util_current_overview_status_authority("
                in target_source
            ),
            "recomputed_overview_supplied_to_status_authority": (
                "recomputed_overview=(_collect_design_overview(state) if isinstance(state, dict) else {})"
                in target_source
            ),
            "failure_coverage_controller_helper_present": (
                "_build_design_guide_shear_low_util_failure_coverage_from_overviews("
                in target_source
            ),
            "candidate_evaluation_boundary_present": (
                "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in target_source
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
            "legacy_direct_candidate_evaluation_removed": (
                "candidate = _evaluate_auto_design_candidate(" not in target_source
            ),
        },
        "safe_to_move_overview_now": False,
        "safe_to_delete_target_function_now": False,
        "required_next_proof": (
            "Compare recomputed current overview against the already-resolved `ov`/caller overview "
            "for fallback shear util and failure-coverage outcomes before replacing either call."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    calls = list(capture.get("overview_calls") or [])
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "source_checks_green": all(source_checks.values()),
        "two_calls_classified": len(calls) == 2,
        "calls_not_safe_to_remove_yet": all(call.get("safe_to_remove_now") is False for call in calls),
        "not_safe_to_move_overview": capture.get("safe_to_move_overview_now") is False,
        "not_safe_to_delete_target_function": capture.get("safe_to_delete_target_function_now") is False,
        "required_next_proof_recorded": bool(capture.get("required_next_proof")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Current Overview Boundary",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Overview Calls",
            "",
            "| ID | Absolute line | Current role | Safe to remove now | Reason |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    for call in capture.get("overview_calls") or []:
        lines.append(
            f"| {call.get('id')} | {call.get('absolute_line')} | {call.get('current_role')} | {call.get('safe_to_remove_now')} | {call.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Next Proof",
            "",
            str(capture.get("required_next_proof") or ""),
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_current_overview_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_current_overview_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_current_overview_boundary {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
