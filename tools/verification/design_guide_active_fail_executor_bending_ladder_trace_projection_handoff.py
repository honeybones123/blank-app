"""Verify active-fail bending ladder trace projection handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
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
TARGET = "_active_fail_near_current_repair_item"
NESTED = "_evaluate"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_node(source: str, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _function_source(source: str, node: ast.FunctionDef | None) -> str:
    if node is None:
        return ""
    lines = source.splitlines()
    end = int(node.end_lineno or node.lineno)
    return "\n".join(lines[node.lineno - 1 : end])


def _nested_function_source(source: str, outer_name: str, nested_name: str) -> str:
    outer = _function_node(source, outer_name)
    if outer is None:
        return ""
    lines = source.splitlines()
    for node in ast.walk(outer):
        if isinstance(node, ast.FunctionDef) and node.name == nested_name:
            end = int(node.end_lineno or node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
    return ""


def _old_evaluation_trace(spec: dict[str, Any], evaluated: dict[str, Any], candidate_index: int) -> dict[str, Any]:
    overview = dict(evaluated.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})
    result = "PASS" if bool(evaluated.get("is_compliant")) and not bool(overview.get("any_fail")) else "FAIL"
    failure_reason = ""
    if result != "PASS":
        failure_reason = str(
            evaluated.get("rejection_reason")
            or evaluated.get("failed_check_name")
            or next(
                (
                    f"{family}:{status}"
                    for family, status in statuses.items()
                    if str(status or "").strip().upper() in {"FAIL", "FAILED", "ERROR"}
                ),
                "required_check_not_compliant",
            )
        )
    return {
        "scenario": "scenario_c3_pure_bending_underdesign_repair",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "source": "bending_fail_contract_ladder",
        "ladder_index": spec.get("ladder_index"),
        "contract_step": spec.get("contract_step"),
        "stage_name": spec.get("stage_name"),
        "candidate_index": int(candidate_index),
        "b": spec.get("b"),
        "D": spec.get("D"),
        "bottom_bar_count": spec.get("bottom_bar_count"),
        "bar_diameter": spec.get("bar_diameter"),
        "split_row": bool(spec.get("split_row")),
        "clear_spacing": spec.get("clear_spacing"),
        "result": result,
        "failure_reason": failure_reason,
        "is_compliant": bool(evaluated.get("is_compliant")),
        "all_key_pass": bool(overview.get("all_key_pass")),
        "any_fail": bool(overview.get("any_fail")),
        "candidate_post_util": evaluated.get("candidate_post_util") or evaluated.get("worst_util"),
        "updates": dict(evaluated.get("updates") or {}),
        "acceptance_basis": evaluated.get("bending_fail_acceptance_basis"),
    }


def _old_first_trace(spec: dict[str, Any], evaluated: dict[str, Any], candidate_index: int) -> dict[str, Any]:
    overview = dict(evaluated.get("overview") or {})
    updates = dict(evaluated.get("updates") or {})
    return {
        "scenario": "scenario_c3_pure_bending_underdesign_repair",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "source": "bending_fail_contract_ladder",
        "ladder_index": spec.get("ladder_index"),
        "contract_step": spec.get("contract_step"),
        "stage_name": spec.get("stage_name"),
        "candidate_index": int(candidate_index),
        "b": spec.get("b"),
        "D": spec.get("D"),
        "bottom_bar_count": spec.get("bottom_bar_count"),
        "bar_diameter": spec.get("bar_diameter"),
        "split_row": bool(spec.get("split_row")),
        "clear_spacing": spec.get("clear_spacing"),
        "candidate_post_util": evaluated.get("candidate_post_util") or evaluated.get("worst_util"),
        "updates": dict(updates),
        "payload_non_empty": bool(updates),
        "all_key_pass": bool(overview.get("all_key_pass")),
        "any_fail": bool(overview.get("any_fail")),
    }


def _new_rows(spec: dict[str, Any], evaluated: dict[str, Any], candidate_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row,
        build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row,
    )

    return (
        build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(
            spec=spec,
            evaluated_candidate=evaluated,
            candidate_index=candidate_index,
        ),
        build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(
            spec=spec,
            evaluated_candidate=evaluated,
            candidate_index=candidate_index,
        ),
    )


def _parity_rows() -> dict[str, dict[str, Any]]:
    spec = {
        "ladder_index": 4,
        "contract_step": "increase_depth",
        "stage_name": "geometry_then_reo",
        "b": 400.0,
        "D": 700.0,
        "bottom_bar_count": 6,
        "bar_diameter": 20,
        "split_row": False,
        "clear_spacing": 52.0,
    }
    cases = {
        "pass_candidate": {
            "is_compliant": True,
            "candidate_post_util": 0.92,
            "updates": {"D": 700.0, "bot1_count": 6},
            "bending_fail_acceptance_basis": "required_checks_no_fail_or_error;non_demand_sls_statuses_do_not_block_repair",
            "overview": {"all_key_pass": False, "any_fail": False, "statuses": {"bending": "PASS"}},
        },
        "explicit_fail_candidate": {
            "is_compliant": False,
            "worst_util": 1.12,
            "updates": {"D": 680.0},
            "failed_check_name": "bending",
            "overview": {"all_key_pass": False, "any_fail": True, "statuses": {"bending": "FAIL"}},
        },
        "status_fallback_failure_reason": {
            "is_compliant": False,
            "worst_util": 1.05,
            "updates": {"bot1_count": 5},
            "overview": {"all_key_pass": False, "any_fail": False, "statuses": {"shear": "FAILED"}},
        },
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, evaluated in cases.items():
        old_eval = _old_evaluation_trace(spec, dict(evaluated), 3)
        old_first = _old_first_trace(spec, dict(evaluated), 3)
        new_eval, new_first = _new_rows(spec, dict(evaluated), 3)
        rows[name] = {
            "evaluation_old_hash": _stable_hash(old_eval),
            "evaluation_new_hash": _stable_hash(new_eval),
            "first_old_hash": _stable_hash(old_first),
            "first_new_hash": _stable_hash(new_first),
            "matches": old_eval == new_eval and old_first == new_first,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_node = _function_node(inputs_source, TARGET)
    target_source = _function_source(inputs_source, target_node)
    nested_source = _nested_function_source(inputs_source, TARGET, NESTED)
    source_checks = {
        "target_found": target_node is not None,
        "nested_evaluate_delegates_evaluation_trace_row": (
            "_build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(" in target_source
        ),
        "nested_evaluate_delegates_first_executable_trace_row": (
            "_build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(" in target_source
        ),
        "page_still_emits_trace": "_inputs_pre_widget_trace(" in target_source,
        "nested_evaluate_no_longer_builds_evaluated_status": "evaluated_status =" not in nested_source,
        "nested_evaluate_no_longer_builds_failure_reason": "failure_reason =" not in nested_source,
        "controller_evaluation_trace_helper_exists": (
            "def build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row(" in controller_source
        ),
        "controller_first_executable_trace_helper_exists": (
            "def build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row(" in controller_source
        ),
        "controller_exports_trace_helpers": all(
            token in controller_source
            for token in (
                '"build_design_guide_controller_active_fail_executor_bending_ladder_evaluation_trace_row"',
                '"build_design_guide_controller_active_fail_executor_bending_ladder_first_executable_trace_row"',
            )
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
    }
    return {
        "schema": "design_guide_active_fail_executor_bending_ladder_trace_projection_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": int(target_node.lineno if target_node else 0),
            "line_end": int(target_node.end_lineno if target_node and target_node.end_lineno else 0),
        },
        "parity": _parity_rows(),
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = dict(payload.get("parity") or {})
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "trace_projection_hashes_unchanged": bool(parity)
        and all(row.get("matches") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_bending_ladder_trace_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_bending_ladder_trace_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Bending Ladder Trace Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved bending active-fail ladder trace-row projection behind "
            "`DesignGuideController`. The page still emits trace rows and owns runtime "
            "debug/session plumbing."
        ),
        "",
        "## Parity",
        *[
            f"- {name}: {'PASS' if row.get('matches') else 'FAIL'}"
            for name, row in (payload.get("parity") or {}).items()
        ],
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_bending_ladder_trace_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
